from .base import Draft, Evidence, RuleBase
from .r001 import R001
from .r002 import R002
from .r003 import R003
from .r004 import R004
from .r005 import R005
from .r006 import R006
from .r007 import R007

ALL_RULES: list[RuleBase] = [R001(), R002(), R003(), R004(), R005(), R006(), R007()]

__all__ = ["ALL_RULES", "Draft", "Evidence", "RuleBase"]
