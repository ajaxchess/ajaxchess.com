# ── Site-wide theme settings ──────────────────────────────────────────────────
from datetime import date, datetime, timedelta

DEFAULT_SKIN: str = 'dark'
ALLOWED_SKINS: tuple[str, ...] = ('dark',)

# ── World Chess Day theming (July 20) ─────────────────────────────────────────
CHESS_DAY_BANNER: str = "Happy World Chess Day! ♟ July 20 — recognized by the United Nations."

# ── Solstice / Equinox theming ────────────────────────────────────────────────
SOLSTICE_BANNER:  str = "Happy Solstice! ♟ The longest (or shortest) day of the year."
EQUINOX_BANNER:   str = "Happy Equinox! ♟ Day and night are nearly equal today."


def _astronomical_dates(year: int) -> tuple[date, date, date, date]:
    """Return (march_equinox, june_solstice, september_equinox, december_solstice)
    for the given year.  Uses the Meeus simplified formula."""
    Y = (year - 2000) / 1000.0
    march_jde = (2451623.80984
                 + 365242.37404 * Y
                 + 0.05169      * Y ** 2
                 - 0.00411      * Y ** 3
                 - 0.00057      * Y ** 4)
    june_jde  = (2451716.567
                 + 365241.62603 * Y
                 + 0.00325      * Y ** 2
                 + 0.00888      * Y ** 3
                 - 0.00030      * Y ** 4)
    sep_jde   = (2451810.21715
                 + 365242.01767 * Y
                 - 0.11575      * Y ** 2
                 + 0.00337      * Y ** 3
                 + 0.00078      * Y ** 4)
    dec_jde   = (2451900.05952
                 + 365242.74049 * Y
                 - 0.06223      * Y ** 2
                 - 0.00823      * Y ** 3
                 + 0.00032      * Y ** 4)
    epoch = datetime(2000, 1, 1, 12)
    to_date = lambda jde: (epoch + timedelta(days=jde - 2451545.0)).date()
    return to_date(march_jde), to_date(june_jde), to_date(sep_jde), to_date(dec_jde)


def is_solstice_today() -> bool:
    today = date.today()
    _, june_sol, _, dec_sol = _astronomical_dates(today.year)
    return today in (june_sol, dec_sol)


def is_equinox_today() -> bool:
    today = date.today()
    march_eq, _, sep_eq, _ = _astronomical_dates(today.year)
    return today in (march_eq, sep_eq)


def is_chess_day() -> bool:
    """Return True if today is World Chess Day — July 20."""
    today = date.today()
    return today.month == 7 and today.day == 20


def active_skin() -> str:
    return DEFAULT_SKIN


def solstice_banner() -> str | None:
    return SOLSTICE_BANNER if is_solstice_today() else None


def equinox_banner() -> str | None:
    return EQUINOX_BANNER if is_equinox_today() else None


def chess_day_banner() -> str | None:
    return CHESS_DAY_BANNER if is_chess_day() else None
