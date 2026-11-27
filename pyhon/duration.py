import ast
import json
import math
import operator
import re
from typing import Any, Callable, Dict, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from pyhon.appliance import HonAppliance
    from pyhon.commands import HonCommand

_OPT_KEY_RE = re.compile(r"^opt\d+$")
_DECIMAL_COMMA_RE = re.compile(r"(\d),(\d)")
_TOKEN_RE = re.compile(r"#?[A-Za-z_][A-Za-z0-9_]*")
_MAX_DEPTH = 20

_DRY_PROGRAM_TYPES = frozenset({"SD", "WD", "W+D", "D"})
_HQD_PLATFORMS = frozenset({"HQD"})

_BIN_OPS: Dict[type[ast.operator], Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}
_UNARY_OPS: Dict[type[ast.unaryop], Callable[[float], float]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _is_number(value: Any) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, (int, float)):
        return math.isfinite(value)
    if isinstance(value, str) and value.strip() != "":
        try:
            return math.isfinite(float(value))
        except ValueError:
            return False
    return False


def _format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _eval_ast_node(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval_ast_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        if isinstance(node.value, bool):
            raise ValueError("Boolean constant not allowed")
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_ast_node(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        left = _eval_ast_node(node.left)
        right = _eval_ast_node(node.right)
        return _BIN_OPS[type(node.op)](left, right)
    raise ValueError(f"Unsupported expression node: {type(node).__name__}")


def _eval_arithmetic(expression: str) -> float:
    tree = ast.parse(expression, mode="eval")
    result = _eval_ast_node(tree)
    if not math.isfinite(result):
        raise ValueError("Non-finite arithmetic result")
    return result


def normalize_model_attributes(appliance_model: Dict[str, Any]) -> Dict[str, str]:
    """Extract applianceModel.attributes into a flat {parName: parValue} mapping."""
    raw = appliance_model.get("attributes")
    if isinstance(raw, dict):
        return {str(k): str(v) for k, v in raw.items() if v is not None}
    if not isinstance(raw, list):
        return {}
    result: Dict[str, str] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = item.get("parName")
        value = item.get("parValue")
        if name is not None and value is not None:
            result[str(name)] = str(value)
    return result


def _match_pipe_key(target: str, mapping: Dict[str, Any]) -> Optional[str]:
    if target in mapping and target != "default":
        return target
    for key in mapping:
        if key == "default":
            continue
        if target in [part.strip() for part in key.split("|")]:
            return key
    return None


def _select_remaining_time_attr(model_attrs: Dict[str, str]) -> Optional[str]:
    formula = model_attrs.get("remainingTime")
    for key in ("remainingTime3", "remainingTime4", "remainingTime2"):
        if candidate := model_attrs.get(key):
            formula = candidate
    return formula


def _resolve_broken_branch(
    branches: Dict[str, Any], param_val: Optional[str]
) -> Optional[str]:
    if param_val is not None:
        if matched := _match_pipe_key(param_val, branches):
            return str(branches[matched])
    default_val = branches.get("default")
    return str(default_val) if default_val is not None else None


def _break_remaining_times(raw: Optional[str], params: Dict[str, str]) -> Optional[str]:
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return raw
    if not isinstance(parsed, dict) or not parsed:
        return raw
    first_key = next(iter(parsed))
    branches = parsed[first_key]
    if not isinstance(branches, dict):
        return raw
    return _resolve_broken_branch(branches, params.get(first_key))


def _extract_command_params(
    command: "HonCommand", options: Dict[str, Any]
) -> Tuple[Dict[str, str], Dict[str, str]]:
    params: Dict[str, str] = {}
    ancillary: Dict[str, str] = {}
    for key, parameter in command.parameters.items():
        if parameter.group == "parameters":
            params[key] = _format_value(parameter.intern_value)
        elif parameter.group == "ancillaryParameters":
            ancillary[key] = _format_value(parameter.intern_value)
    _apply_selection_overrides(params, ancillary, options)
    return params, ancillary


def _apply_selection_overrides(
    params: Dict[str, str], ancillary: Dict[str, str], options: Dict[str, Any]
) -> None:
    if "permanentPressStatus" in params:
        params["permanentPressStatus"] = "0"
    dry_level = params.get("dryLevel", "")
    if _is_number(dry_level) and float(dry_level) > 0:
        params["dryTime"] = "0"
    dry_time = params.get("dryTime", "")
    if dry_time and dry_time != "0":
        params["dryLevel"] = "0"
    if ancillary.get("programType") in _DRY_PROGRAM_TYPES:
        params["dryProgFlag"] = "1"
    for opt_key, param_name in options.items():
        if _OPT_KEY_RE.match(opt_key) and opt_key not in params:
            params[opt_key] = params.get(str(param_name), "0")


def _extract_remaining_times(command: "HonCommand") -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, parameter in command.parameters.items():
        if parameter.group == "remainingTimes":
            result[key] = parameter.intern_value
    for key, value in command.data.items():
        if key not in result:
            result[key] = value
    return result


def _normalize_remaining_time_obj(value: Any) -> Any:
    if not isinstance(value, dict) or len(value) != 1:
        return value
    only_val = next(iter(value.values()))
    if not isinstance(only_val, str):
        return value
    try:
        return json.loads(only_val.replace(";", ","))
    except ValueError:
        return value


class _HqdDurationEvaluator:  # pylint: disable=too-few-public-methods
    """Evaluates hOn HQD applianceModel.attributes remainingTime expressions."""

    def __init__(
        self,
        params: Dict[str, str],
        ancillary: Dict[str, str],
        model_attrs: Dict[str, str],
        remaining_times: Dict[str, Any],
    ) -> None:
        self._params = params
        self._ancillary = ancillary
        self._model_attrs = model_attrs
        self._remaining_times = remaining_times

    def evaluate(self) -> Optional[int]:
        raw_formula = _select_remaining_time_attr(self._model_attrs)
        formula = _break_remaining_times(raw_formula, self._params)
        if not formula:
            return None
        normalized = _DECIMAL_COMMA_RE.sub(r"\1.\2", formula)
        substituted = _TOKEN_RE.sub(self._replace_global_token, normalized)
        try:
            total = _eval_arithmetic(substituted)
        except (ValueError, ZeroDivisionError, SyntaxError):
            return None
        if total <= 0:
            return None
        return int(round(total))

    def _replace_global_token(self, match: "re.Match[str]") -> str:
        token = match.group(0)
        stripped = token.lstrip("#")
        target: Any = None
        if raw_attr := self._model_attrs.get(stripped):
            try:
                target = json.loads(raw_attr)
            except ValueError:
                target = raw_attr
        else:
            target = self._params.get(token) or self._ancillary.get(token)
        if target is None:
            return "0"
        value = self._recursive_search(target, do_round=False, depth=0)
        return str(value) if math.isfinite(value) else "0"

    def _resolve_hash_attr(self, key: str, depth: int) -> Any:
        raw = self._model_attrs.get(key[1:])
        if isinstance(raw, str) and raw.startswith("{"):
            try:
                parsed = json.loads(raw)
            except ValueError:
                return raw
            return self._recursive_search(parsed, do_round=False, depth=depth + 1)
        return raw

    def _resolve_param(
        self, key: str, depth: int, from_remaining_times: bool = False
    ) -> Any:
        if "#" in key:
            return self._resolve_hash_attr(key, depth)
        if from_remaining_times and key in self._remaining_times:
            return _normalize_remaining_time_obj(self._remaining_times[key])
        if val := (self._params.get(key) or self._ancillary.get(key)):
            return val
        if key == "round":
            return "round"
        return "0" if _OPT_KEY_RE.match(key) else None

    def _split_remaining_time_param(self, key: str, depth: int) -> Any:
        parts = key.split("remainingTime", 1)
        if len(parts) < 2 or not parts[1]:
            return None
        suffix = parts[1]
        param_name = suffix[0].lower() + suffix[1:]
        table = self._resolve_param(param_name, depth, from_remaining_times=True)
        current = self._resolve_param(param_name, depth)
        if not current or not isinstance(table, dict):
            return None
        return table.get(str(current))

    def _calculate_expression(self, expr: str, do_round: bool, depth: int) -> float:
        normalized = _DECIMAL_COMMA_RE.sub(r"\1.\2", expr)

        def replace(match: "re.Match[str]") -> str:
            return self._resolve_expr_token(match.group(0), do_round, depth)

        substituted = _TOKEN_RE.sub(replace, normalized)
        try:
            result = _eval_arithmetic(substituted)
        except (ValueError, ZeroDivisionError, SyntaxError):
            return 0.0
        return float(round(result)) if do_round else result

    def _resolve_expr_token(self, token: str, do_round: bool, depth: int) -> str:
        if "#" in token:
            raw = self._model_attrs.get(token[1:])
            if raw is not None and _is_number(raw):
                return str(float(raw))
            if isinstance(raw, str):
                try:
                    parsed = json.loads(raw)
                except ValueError:
                    return "0"
                return str(self._recursive_search(parsed, do_round, depth + 1))
            return "0"
        val = self._resolve_param(token, depth)
        return str(float(val)) if _is_number(val) else "0"

    def _search_dict(self, node: Dict[str, Any], do_round: bool, depth: int) -> float:
        for key, sub in node.items():
            if key == "round":
                do_round = True
                continue
            if _is_number(sub):
                return float(round(float(sub))) if do_round else float(sub)
            if isinstance(sub, str):
                return self._calculate_expression(sub, do_round, depth + 1)
            if isinstance(sub, dict):
                return self._search_branch(key, sub, do_round, depth)
        return 0.0

    def _search_branch(
        self, key: str, sub: Dict[str, Any], do_round: bool, depth: int
    ) -> float:
        resolved = self._resolve_param(key, depth)
        if resolved is None:
            return self._search_missing_branch(sub, do_round, depth)
        resolved_str = _format_value(resolved)
        if matched := _match_pipe_key(resolved_str, sub):
            return self._recursive_search(sub[matched], do_round, depth + 1)
        if "default" in sub:
            return self._recursive_search(sub["default"], do_round, depth + 1)
        if "suggestedLoad" in key and _is_number(resolved):
            num = float(resolved)
            return float(round(num)) if do_round else num
        return 0.0

    def _search_missing_branch(
        self, sub: Dict[str, Any], do_round: bool, depth: int
    ) -> float:
        if "undefined" in sub:
            return self._recursive_search(sub["undefined"], do_round, depth + 1)
        if "default" in sub:
            return self._recursive_search(sub["default"], do_round, depth + 1)
        return 0.0

    def _recursive_search(self, node: Any, do_round: bool, depth: int) -> float:
        if depth > _MAX_DEPTH:
            return 0.0
        if isinstance(node, dict):
            return self._search_dict(node, do_round, depth)
        if _is_number(node):
            num = float(node)
            return float(round(num)) if do_round else num
        if isinstance(node, str):
            return self._search_string(node, do_round, depth)
        return 0.0

    def _search_string(self, node: str, do_round: bool, depth: int) -> float:
        if "remainingTime" in node and "remainingTimeSoftening" not in node:
            sub = self._split_remaining_time_param(node, depth)
            return self._recursive_search(sub, do_round, depth + 1)
        return self._calculate_expression(node, do_round, depth + 1)


def is_hqd_duration_supported(appliance: "HonAppliance") -> bool:
    """Return True if the appliance exposes an HQD remainingTime formula."""
    if "startProgram" not in appliance.commands:
        return False
    model_attrs = normalize_model_attributes(appliance.appliance_model)
    if model_attrs.get("platform") not in _HQD_PLATFORMS:
        return False
    return _select_remaining_time_attr(model_attrs) is not None


def calculate_hqd_duration(appliance: "HonAppliance") -> Optional[int]:
    """Calculate dynamic pre-start cycle duration in minutes for HQD appliances."""
    if not (command := appliance.commands.get("startProgram")):
        return None
    model_attrs = normalize_model_attributes(appliance.appliance_model)
    if model_attrs.get("platform") not in _HQD_PLATFORMS:
        return None
    params, ancillary = _extract_command_params(command, appliance.options)
    remaining_times = _extract_remaining_times(command)
    evaluator = _HqdDurationEvaluator(
        params=params,
        ancillary=ancillary,
        model_attrs=model_attrs,
        remaining_times=remaining_times,
    )
    return evaluator.evaluate()
