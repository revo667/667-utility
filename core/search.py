import re
import subprocess

TOKEN_RE = re.compile(r"\b[A-Za-z0-9][A-Za-z0-9_.\-]*\.[A-Za-z0-9_.\-]+\b")
ANSI_RE = re.compile(r"\x1B[@-_][0-?]*[ -/]*[@-~]")

def _clean(text: str) -> str:
    if not text:
        return ""
    t = ANSI_RE.sub("", text)
    t = t.replace("\u00A0", " ")
    return t

def search_first_package_id(query: str) -> tuple[bool, str]:
    if not query or not query.strip():
        return False, "Boş arama yapılamaz"
    try:
        proc = subprocess.run(
            ["winget", "search", query, "--accept-source-agreements"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        stdout = _clean(proc.stdout or "")
        stderr = _clean(proc.stderr or "")
        content = (stdout + "\n" + stderr).strip()
        lines = [line for line in content.splitlines() if line.strip()]
        if not lines:
            return False, "Result not find"
        header_idx = None
        for i, line in enumerate(lines):
            low = line.lower()
            if "name" in low and "id" in low:
                header_idx = i
                break
        candidates = []
        if header_idx is not None:
            for line in lines[header_idx + 1:]:
                if set(re.sub(r"\s", "", line)) == {"-"}:
                    continue
                parts = re.split(r"\s{2,}", line.strip())
                if len(parts) >= 2:
                    cand = parts[1].strip()
                    if TOKEN_RE.fullmatch(cand):
                        candidates.append(cand)
                    else:
                        found = TOKEN_RE.findall(parts[1])
                        if found:
                            candidates.extend(found)
                else:
                    found = TOKEN_RE.findall(line)
                    if found:
                        candidates.extend(found)
        if not candidates:
            qlow = query.lower()
            for i, line in enumerate(lines):
                if qlow in line.lower():
                    found = TOKEN_RE.findall(line)
                    if found:
                        candidates.extend(found)
                        break
                    if i + 1 < len(lines):
                        found2 = TOKEN_RE.findall(lines[i + 1])
                        if found2:
                            candidates.extend(found2)
                            break
                    if i - 1 >= 0:
                        found3 = TOKEN_RE.findall(lines[i - 1])
                        if found3:
                            candidates.extend(found3)
                            break
        if not candidates:
            for line in lines:
                found = TOKEN_RE.findall(line)
                if found:
                    candidates.extend(found)
                    break
        if not candidates:
            for line in lines:
                parts = re.split(r"\s{2,}", line.strip())
                for p in parts:
                    if "." in p and any(c.isalnum() for c in p):
                        candidates.append(p.strip())
                if candidates:
                    break
        if not candidates:
            return False, "Result not find"
        return True, candidates[0]
    except FileNotFoundError:
        return False, "winget cant find"
    except Exception as e:
        return False, str(e)
