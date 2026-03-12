from bs4 import BeautifulSoup  # type: ignore[import-untyped]


def html_to_text(html: str) -> str:
    """
    Rydder vekk HTML og henter ut lesbar tekst.
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def normalize_email_body(body: str, is_html: bool = True) -> str:
    if is_html:
        return html_to_text(body)
    return body

