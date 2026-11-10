"""R004: loyiha qiymati ish qiymatidan past."""
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
                low = min(design, key=lambda p: p.si_value)
                high = max(operating, key=lambda p: p.si_value)
                if low.si_value >= high.si_value - EPS:
                    continue
                drafts.append(Draft(
                    self.code, tag_id, low.tag.tag, design_name, Severity.critical, Confidence.high,
                    "r004_design_below_operating",
                    {"tag": low.tag.tag, "param": design_name, "operating_param": operating_name,
                     "design": f"{doc_label(low.document)}: {display_value(low)}",
                     "operating": f"{doc_label(high.document)}: {display_value(high)}"},
                    [param_evidence(low), param_evidence(high)]))
        return drafts
