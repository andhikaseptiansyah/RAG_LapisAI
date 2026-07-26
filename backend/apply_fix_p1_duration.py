from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil
import sys

TARGET = Path('api/answer_formatter.py')

ANCHOR_1 = '''    scored: list[tuple[int, int, object]] = []
    for index, match in enumerate(matches):
        sentence = normalize_text(_sentence_window(text, match.start(), match.end()))

        # Focus action matching on the text immediately preceding the scalar.
'''

REPLACEMENT_1 = '''    normalized_question = normalize_text(question)
    asks_for_escalation = any(
        term in normalized_question
        for term in (
            "escalated", "escalation", "escalate",
            "dieskalasikan", "eskalasi", "mengeskalasi",
        )
    )

    scored: list[tuple[int, int, object]] = []
    for index, match in enumerate(matches):
        sentence = normalize_text(_sentence_window(text, match.start(), match.end()))

        # A policy paragraph may contain both the actual resolution SLA and an
        # earlier escalation trigger, for example: "resolved within 4 hours"
        # followed by "if not resolved within 2 hours, escalate". Both values
        # mention P1 and resolution, so without this distinction they tie and
        # the safe scalar fallback returns nothing.
        conditional_escalation = bool(
            (
                any(term in sentence for term in ("if ", "jika "))
                and any(
                    term in sentence
                    for term in (
                        "not resolved", "not completed",
                        "belum diselesaikan", "tidak diselesaikan",
                    )
                )
            )
            or any(
                term in sentence
                for term in (
                    "is escalated", "will be escalated", "escalated to",
                    "akan dieskalasikan", "harus dieskalasikan",
                )
            )
        )

        # Focus action matching on the text immediately preceding the scalar.
'''

ANCHOR_2 = '''        for anchor in action_anchors:
            anchor_pos = action_window.rfind(normalize_text(anchor))
            if anchor_pos >= 0:
                distance = max(len(action_window) - anchor_pos, 1)
                score = max(score, 190 - min(distance, 175))

        if requested_code:
'''

REPLACEMENT_2 = '''        for anchor in action_anchors:
            anchor_pos = action_window.rfind(normalize_text(anchor))
            if anchor_pos >= 0:
                distance = max(len(action_window) - anchor_pos, 1)
                score = max(score, 190 - min(distance, 175))

        if asks_for_escalation:
            score += 300 if conditional_escalation else -120
        elif conditional_escalation:
            # The user asked for the resolution deadline, not the escalation
            # checkpoint. Keep the checkpoint retrievable for escalation
            # questions, but do not let it tie the actual SLA target.
            score -= 300
        elif any(
            term in sentence
            for term in (
                "must be resolved", "resolution target", "resolved within",
                "harus diselesaikan", "target penyelesaian",
            )
        ):
            score += 90

        if requested_code:
'''


def main() -> int:
    if not TARGET.exists():
        print(f'ERROR: {TARGET} tidak ditemukan. Jalankan script dari folder backend.')
        return 1

    text = TARGET.read_text(encoding='utf-8')
    if 'asks_for_escalation = any(' in text:
        print('Patch sudah terpasang. Tidak ada perubahan yang dilakukan.')
        return 0

    if ANCHOR_1 not in text or ANCHOR_2 not in text:
        print('ERROR: Struktur answer_formatter.py berbeda. Patch dibatalkan agar file tidak rusak.')
        return 2

    backup = TARGET.with_suffix(
        TARGET.suffix + '.backup_' + datetime.now().strftime('%Y%m%d_%H%M%S')
    )
    shutil.copy2(TARGET, backup)

    text = text.replace(ANCHOR_1, REPLACEMENT_1, 1)
    text = text.replace(ANCHOR_2, REPLACEMENT_2, 1)
    TARGET.write_text(text, encoding='utf-8')

    print(f'Patch berhasil dipasang: {TARGET}')
    print(f'Backup dibuat: {backup}')
    print('Restart backend, lalu jalankan test regresi.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
