import re
import subprocess


def search_first_package_id(query: str) -> tuple[bool, str]:
    if not query.strip():
        return False, "Boş arama yapılamaz"

    try:
        result = subprocess.run(
            ["winget", "search", query, "--accept-source-agreements"],
            check=True,
            capture_output=True,
            text=True,
        )

        rows = []
        for line in result.stdout.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("Name"):
                continue
            if set(stripped) == {"-"}:
                continue
            rows.append(stripped)

        if not rows:
            return False, "Result not find"

        first_row = rows[0]
        parts = re.split(r"\s{2,}", first_row)
        if len(parts) < 2:
            return False, "none"

        return True, parts[1]
    except subprocess.CalledProcessError:
        return False, "Winget search error"
    except FileNotFoundError:
        return False, "winget cant find"