
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


def get_repositories():
    """Get repositories owned by the user and repositories in organizations."""
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

    # Remove duplicate repositories
    unique = {}
    for repo in repos:
        unique[repo["full_name"]] = repo

    return list(unique.values())


def get_language_bytes(owner, repo):
    """Get language byte counts for a repository."""
    response = session.get(
        f"{API}/repos/{owner}/{repo}/languages"
    )

    if response.status_code == 404:
        return {}

    response.raise_for_status()
    return response.json()


def calculate_languages(repositories):
    totals = defaultdict(int)

    for repo in repositories:
        if repo.get("fork"):
            continue

        full_name = repo["full_name"]

        if "/" not in full_name:
            continue

        owner, name = full_name.split("/", 1)

        try:
            languages = get_language_bytes(owner, name)

            for language, bytes_count in languages.items():
                totals[language] += bytes_count

        except requests.RequestException as error:
            print(f"[WARNING] Could not read {full_name}: {error}")

    return totals


def create_svg(languages, output_file):
    total = sum(byte_count for _, byte_count in languages)

    width = 600
    height = 100 + (len(languages) * 34)

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" rx="10" fill="#0d1117"/>',
        '<text x="30" y="40" fill="#ffffff" font-size="24" font-family="Arial, sans-serif" font-weight="bold">Most Used Languages</text>',
    ]

    y = 75

    for language, byte_count in languages:
        percentage = (byte_count / total) * 100

        label = escape(language)

        svg.append(
            f'<text x="30" y="{y}" fill="#c9d1d9" font-size="16" font-family="Arial, sans-serif">'
            f'{label}</text>'
        )

        svg.append(
            f'<text x="540" y="{y}" fill="#8b949e" font-size="16" '
            f'font-family="Arial, sans-serif" text-anchor="end">'
            f'{percentage:.1f}%</text>'
        )

        svg.append(
            f'<rect x="30" y="{y + 8}" width="510" height="6" rx="3" '
            f'fill="#30363d"/>'
        )

        svg.append(
            f'<rect x="30" y="{y + 8}" width="{510 * percentage / 100:.2f}" '
            f'height="6" rx="3" fill="#58a6ff"/>'
        )

        y += 34

    svg.append("</svg>")

    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as file:
        file.write("\n".join(svg))


def main():
    print(f"[INFO] Collecting repositories for {USERNAME}...")

    repositories = get_repositories()

    print(f"[INFO] Found {len(repositories)} accessible repositories.")

    totals = calculate_languages(repositories)

    if not totals:
        raise RuntimeError(
            "No programming-language data was found. "
            "Check repository access and GitHub token permissions."
        )

    # Show the top 8 languages
    top_languages = sorted(
        totals.items(),
        key=lambda item: item[1],
        reverse=True,
    )[:8]

    print("[INFO] Top languages:")

    for language, byte_count in top_languages:
        percentage = (byte_count / sum(totals.values())) * 100
        print(f"  {language}: {percentage:.1f}%")

    create_svg(
        top_languages,
        "profile/top-langs.svg",
    )

    print("[SUCCESS] Created profile/top-langs.svg")


if __name__ == "__main__":
    main()

