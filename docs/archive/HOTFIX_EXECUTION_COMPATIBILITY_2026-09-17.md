# BARON Hotfix — ExecutionService legacy close compatibility

## Root cause
`ExecutionService.act()` previously called `core.close_position_full()` with `close_price` and `stage` unconditionally. Legacy test doubles/adapters can expose the historical zero-argument callable, causing:

`TypeError: ... got an unexpected keyword argument 'close_price'`

## Fix
`execution/execution_service.py` now inspects the callable signature before invocation and only supplies supported keywords. It preserves the documented current core contract while remaining compatible with legacy zero-argument adapters.

The adapter does not catch `TypeError` from inside the real close function, so genuine implementation errors are not hidden.

## Validation
- Legacy zero-argument close callable: PASS
- Current `(close_price=None, stage='FULL')` callable: PASS
- Stage-only callable: PASS
- `python -m py_compile execution/execution_service.py`: PASS
- Archive integrity (`unzip -t`): PASS
