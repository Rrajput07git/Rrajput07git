
import os
import requests
from collections import defaultdict
from xml.sax.saxutils import escape

TOKEN = os.environ["GITHUB_TOKEN"]
USERNAME = os.environ["GITHUB_USERNAME"]

API = "https://api.github.com"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

session = requests.Session()
session.headers.update(HEADERS)


# File extensions mapped to programming languages.
LANGUAGE_MAP = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "SCSS",
    ".less": "CSS",
    ".php": "PHP",
    ".java": "Java",
    ".c": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".h": "C",
    ".hpp": "C++",
    ".cs": "C#",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".dart": "Dart",
    ".sql": "SQL",
    ".sh": "Shell",
    ".bash": "Shell",
    ".yml": "YAML",
    ".yaml": "YAML",
    ".json": "JSON",
    ".xml": "XML",
    ".vue": "Vue",
}


def get_repositories():
    """Get repositories accessible to the authenticated user."""
    repos = []
    page = 1

    while True:
        response = session.get(
            f"{API}/user/repos",
            params={
                "per_page": 100,
                "page": page,
                "affiliation": "owner,collaborator,organization_member",
                "visibility": "all",
            },
        )
        response.raise_for_status()

        data = response.json()

        if not data:
            break

        repos.extend(data)
        page += 1

    unique = {}

    for repo in repos:
        unique[repo["full_name"]] = repo

    return list(unique.values())


def get_my_commits(owner, repo):
    """
    Get commits authored by the GitHub user.
    We use the author parameter so commits from organization
    repositories can also be included when accessible.
    """
    commits = []
    page = 1

    while True:
        response = session.get(
            f"{API}/repos/{owner}/{repo}/commits",
            params={
                "author": USERNAME,
                "per_page": 100,
                "page": page,
            },
        )

        if response.status_code == 409:
            # Empty repository
            return commits

        if response.status_code == 404:
            return commits

        response.raise_for_status()

        data = response.json()

        if not data:
            break

        commits.extend(data)
        page += 1

    return commits


def get_commit_details(owner, repo, sha):
    """Get files changed in a specific commit."""
    response = session.get(
        f"{API}/repos/{owner}/{repo}/commits/{sha}"
    )

    if response.status_code in (404, 409):
        return None

    response.raise_for_status()

    return response.json()


def language_from_filename(filename):
    """Return our language name from a file extension."""
    filename_lower = filename.lower()

    for extension, language in LANGUAGE_MAP.items():
        if filename_lower.endswith(extension):
            return language

    return None


def calculate_personal_languages(repositories):
    """
    Calculate language usage based on files changed by the user's
    own commits.

    Added/deleted line counts are used as a weight. This makes the
    result reflect the amount of code changed rather than simply
    counting repositories.
    """
    totals = defaultdict(int)

    for index, repo in enumerate(repositories, start=1):
        full_name = repo["full_name"]

        if "/" not in full_name:
            continue

        owner, name = full_name.split("/", 1)

        print(
            f"[INFO] Checking {index}/{len(repositories)}: {full_name}"
        )

        try:
            commits = get_my_commits(owner, name)

            print(
                f"[INFO] Found {len(commits)} commits by {USERNAME}"
            )

            for commit in commits:
                sha = commit["sha"]

                details = get_commit_details(
                    owner,
                    name,
                    sha,
                )

                if not details:
                    continue

                for file in details.get("files", []):
                    filename = file.get("filename", "")
                    language = language_from_filename(filename)

                    if not language:
                        continue

                    additions = file.get("additions", 0)
                    deletions = file.get("deletions", 0)

                    weight = additions + deletions

                    # Give a minimum weight to files that were changed
                    # but have no line statistics.
                    if weight <= 0:
                        weight = 1

                    totals[language] += weight

        except requests.RequestException as error:
            print(
                f"[WARNING] Could not process {full_name}: {error}"
            )

    return totals


def create_svg(languages, output_file):
    """Create the SVG language card."""
    total = sum(byte_count for _, byte_count in languages)

    if total <= 0:
        raise RuntimeError(
            "No personal language activity was found."
        )

    width = 600
    row_height = 34
    height = 100 + (len(languages) * row_height)

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" rx="10" fill="#0d1117"/>',
        '<text x="30" y="40" fill="#ffffff" '
        'font-size="24" font-family="Arial, sans-serif" '
        'font-weight="bold">My Coding Languages</text>',
    ]

    y = 75

    for language, amount in languages:
        percentage = (amount / total) * 100
        label = escape(language)

        svg.append(
            f'<text x="30" y="{y}" fill="#c9d1d9" '
            f'font-size="16" font-family="Arial, sans-serif">'
            f'{label}</text>'
        )

        svg.append(
            f'<text x="540" y="{y}" fill="#8b949e" '
            f'font-size="16" font-family="Arial, sans-serif" '
            f'text-anchor="end">'
            f'{percentage:.1f}%</text>'
        )

        svg.append(
            f'<rect x="30" y="{y + 8}" width="510" '
            f'height="6" rx="3" fill="#30363d"/>'
        )

        bar_width = max(
            0,
            min(510, 510 * percentage / 100),
        )

        svg.append(
            f'<rect x="30" y="{y + 8}" '
            f'width="{bar_width:.2f}" height="6" '
            f'rx="3" fill="#58a6ff"/>'
        )

        y += row_height

    svg.append("</svg>")

    os.makedirs(
        os.path.dirname(output_file),
        exist_ok=True,
    )

    with open(
        output_file,
        "w",
        encoding="utf-8",
    ) as file:
        file.write("\n".join(svg))


def main():
    print(
        f"[INFO] Collecting repositories accessible to "
        f"{USERNAME}..."
    )

    repositories = get_repositories()

    print(
        f"[INFO] Found {len(repositories)} accessible repositories."
    )

    totals = calculate_personal_languages(repositories)

    if not totals:
        raise RuntimeError(
            "No personal coding language data was found. "
            "Make sure the token can access your repositories "
            "and that your commits use the GitHub account/email "
            "associated with this account."
        )

    top_languages = sorted(
        totals.items(),
        key=lambda item: item[1],
        reverse=True,
    )[:8]

    total = sum(totals.values())

    print("[INFO] My coding languages:")

    for language, amount in top_languages:
        percentage = (amount / total) * 100
        print(
            f"  {language}: {percentage:.1f}%"
        )

    create_svg(
        top_languages,
        "profile/top-langs.svg",
    )

    print(
        "[SUCCESS] Created profile/top-langs.svg"
    )


if __name__ == "__main__":
    main()

