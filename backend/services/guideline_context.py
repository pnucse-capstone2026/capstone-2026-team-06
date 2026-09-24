from typing import Dict, List

class GuidelineContext:
    """
    Guideline 검색 결과를 사람이 읽기 쉬운 문자열 형태로 변환
    """

    @staticmethod
    def format_guideline_chunk(chunk: Dict) -> str:
        """
        guideline_search.search()가 반환한 하나의 chunk(dict)를
        [organization - disease] / Section: h1 > h2 > ... / text 형태의 문자열로 변환
        """

        # h1, h2, ... 중 실제 값이 존재하는 header만 사용
        headers = [
            str(chunk[k]).strip()
            for k in sorted(
                (
                    k
                    for k in chunk.keys()
                    if k.startswith("h")
                    and k[1:].isdigit()
                    and chunk.get(k)
                ),
                key=lambda x: int(x[1:])
            )
        ]

        section = " > ".join(headers) if headers else None

        organization = chunk.get("organization") or "Unknown"
        disease = chunk.get("disease") or "Unknown"
        text = chunk.get("text") or ""

        lines = [
            f"[{organization} - {disease}]"
        ]

        if section:
            lines.append(f"Section: {section}")

        lines.append(text)

        return "\n".join(lines)

    @staticmethod
    def format_guidelines(results: List[Dict]) -> str:
        """
        여러 guideline chunk를 하나의 문자열로 변환
        """

        return "\n\n".join(
            GuidelineContext.format_guideline_chunk(chunk)
            for chunk in results
        )