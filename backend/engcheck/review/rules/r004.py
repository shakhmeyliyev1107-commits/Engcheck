"""R004: loyiha qiymati ish sharoitini qamramaydi."""
from collections import defaultdict

from ...core.models import Confidence, Severity
from .base import Draft, RuleBase, display_value, doc_label, param_evidence, project_params

PAIRS = [("design_pressure", "operating_pressure"), ("design_temperature", "operating_temperature")]
EPS = 1e-6


class R004(RuleBase):
    code = "R004"

    def check(self, db, project_id):
        by_tag = defaultdict(lambda: defaultdict(list))
        for p in project_params(db, project_id):
            if p.si_value is not None:
                by_tag[p.tag_id][p.param].append(p)
        drafts = []
        for tag_id, params in by_tag.items():
            for design_name, operating_name in PAIRS:
                design, operating = params.get(design_name), params.get(operating_name)
                if not design or not operating:
                    continue
                maximum = [p for p in design if p.si_value > 0 or design_name == "design_pressure"]
                minimum = [p for p in design if p not in maximum]   # 0 °C va undan past: minimal loyiha harorati
                if maximum:
                    low = min(maximum, key=lambda p: p.si_value)
                    high = max(operating, key=lambda p: p.si_value)
                    if low.si_value < high.si_value - EPS:
                        drafts.append(self._draft(tag_id, low, high, design_name, operating_name,
                                                  "r004_design_below_operating", Confidence.high))
                if minimum:
                    top = max(minimum, key=lambda p: p.si_value)
                    cold = min(operating, key=lambda p: p.si_value)
                    if cold.si_value < top.si_value - EPS:
                        # Qiymat "minimal harorat" ekani hujjatda yozilmagan, belgisidan xulosa qilingan.
                        drafts.append(self._draft(tag_id, top, cold, design_name, operating_name,
                                                  "r004_min_design_above_operating", Confidence.medium))
        return drafts

    def _draft(self, tag_id, design, operating, design_name, operating_name, key, confidence):
        return Draft(
            self.code, tag_id, design.tag.tag, design_name, Severity.critical, confidence, key,
            {"tag": design.tag.tag, "param": design_name, "operating_param": operating_name,
             "design": f"{doc_label(design.document)}: {display_value(design)}",
             "operating": f"{doc_label(operating.document)}: {display_value(operating)}"},
            [param_evidence(design), param_evidence(operating)])
