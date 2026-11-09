"""US-style date formats used by altgen4 providers, stamps and transmission lines.

Every style is month-first or year-first when numeric. Day-first appears only
with a spelled month (e.g. 14-MAR-2025), never as pure digits.
"""
import datetime as dt

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
MON3 = [m[:3] for m in MONTHS]
AP = ["Jan.", "Feb.", "March", "April", "May", "June", "July", "Aug.", "Sept.",
      "Oct.", "Nov.", "Dec."]
MONDOT = ["Jan.", "Feb.", "Mar.", "Apr.", "May", "Jun.", "Jul.", "Aug.", "Sep.",
          "Oct.", "Nov.", "Dec."]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def ordinal(n):
    if 10 <= n % 100 <= 20:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return "%d%s" % (n, suf)


def _h12(h):
    return (h % 12) or 12, ("AM" if h < 12 else "PM")


# pattern label -> function(date, (h, m, s)) ; labels are what the README lists
STYLES = {
    "MM/DD/YYYY":            lambda d, t: "%02d/%02d/%04d" % (d.month, d.day, d.year),
    "M/D/YYYY":              lambda d, t: "%d/%d/%04d" % (d.month, d.day, d.year),
    "M/D/YY":                lambda d, t: "%d/%d/%02d" % (d.month, d.day, d.year % 100),
    "MM/DD/YY":              lambda d, t: "%02d/%02d/%02d" % (d.month, d.day, d.year % 100),
    "MM-DD-YYYY":            lambda d, t: "%02d-%02d-%04d" % (d.month, d.day, d.year),
    "M-D-YY":                lambda d, t: "%d-%d-%02d" % (d.month, d.day, d.year % 100),
    "M.D.YYYY":              lambda d, t: "%d.%d.%04d" % (d.month, d.day, d.year),
    "MM.DD.YY":              lambda d, t: "%02d.%02d.%02d" % (d.month, d.day, d.year % 100),
    "YYYY-MM-DD":            lambda d, t: "%04d-%02d-%02d" % (d.year, d.month, d.day),
    "YYYYMMDD":              lambda d, t: "%04d%02d%02d" % (d.year, d.month, d.day),
    "YYYY/MM/DD":            lambda d, t: "%04d/%02d/%02d" % (d.year, d.month, d.day),
    "Month D, YYYY":         lambda d, t: "%s %d, %d" % (MONTHS[d.month - 1], d.day, d.year),
    "Mon D, YYYY":           lambda d, t: "%s %d, %d" % (MON3[d.month - 1], d.day, d.year),
    "Mon. D, YYYY":          lambda d, t: "%s %d, %d" % (MONDOT[d.month - 1], d.day, d.year),
    "AP Mon. D, YYYY":       lambda d, t: "%s %d, %d" % (AP[d.month - 1], d.day, d.year),
    "MON DD YYYY":           lambda d, t: "%s %02d %d" % (MON3[d.month - 1].upper(), d.day, d.year),
    "DD-MON-YYYY":           lambda d, t: "%02d-%s-%d" % (d.day, MON3[d.month - 1].upper(), d.year),
    "D Mon YYYY":            lambda d, t: "%d %s %d" % (d.day, MON3[d.month - 1], d.year),
    "DDMONYYYY":             lambda d, t: "%02d%s%d" % (d.day, MON3[d.month - 1].upper(), d.year),
    "Mon-DD-YYYY":           lambda d, t: "%s-%02d-%d" % (MON3[d.month - 1], d.day, d.year),
    "Weekday, Month D, YYYY": lambda d, t: "%s, %s %d, %d" % (WEEKDAYS[d.weekday()], MONTHS[d.month - 1], d.day, d.year),
    "Month Dth, YYYY":       lambda d, t: "%s %s, %d" % (MONTHS[d.month - 1], ordinal(d.day), d.year),
    "Dth day of Month, YYYY": lambda d, t: "the %s day of %s, %d" % (ordinal(d.day), MONTHS[d.month - 1], d.year),
    "Dy Mon DD, YYYY":       lambda d, t: "%s %s %02d, %d" % (WEEKDAYS[d.weekday()][:3], MON3[d.month - 1], d.day, d.year),
    # timestamps
    "MM/DD/YYYY HH:MM":      lambda d, t: "%02d/%02d/%04d %02d:%02d" % (d.month, d.day, d.year, t[0], t[1]),
    "M/D/YYYY h:MM AM":      lambda d, t: "%d/%d/%04d %d:%02d %s" % ((d.month, d.day, d.year) + (_h12(t[0])[0], t[1], _h12(t[0])[1])),
    "YYYY-MM-DDTHH:MM:SS":   lambda d, t: "%04d-%02d-%02dT%02d:%02d:%02d" % (d.year, d.month, d.day, t[0], t[1], t[2]),
    "YYYY-MM-DD HH:MM":      lambda d, t: "%04d-%02d-%02d %02d:%02d" % (d.year, d.month, d.day, t[0], t[1]),
    "YYYYMMDD HHMM":         lambda d, t: "%04d%02d%02d %02d%02d" % (d.year, d.month, d.day, t[0], t[1]),
    "MM/DD/YY@HHMM":         lambda d, t: "%02d/%02d/%02d@%02d%02d" % (d.month, d.day, d.year % 100, t[0], t[1]),
    "DD-MON-YYYY HH:MM":     lambda d, t: "%02d-%s-%d %02d:%02d" % (d.day, MON3[d.month - 1].upper(), d.year, t[0], t[1]),
    "Mon D YYYY h:MMam":     lambda d, t: "%s %d %d %d:%02d%s" % (MON3[d.month - 1], d.day, d.year, _h12(t[0])[0], t[1], _h12(t[0])[1].lower()),
}

# date-only styles available for a provider's main (date-of-service) style
DOS_STYLES = ["MM/DD/YYYY", "M/D/YYYY", "M/D/YY", "MM/DD/YY", "MM-DD-YYYY", "M-D-YY",
              "M.D.YYYY", "MM.DD.YY", "YYYY-MM-DD", "YYYYMMDD", "YYYY/MM/DD",
              "Month D, YYYY", "Mon D, YYYY", "Mon. D, YYYY", "AP Mon. D, YYYY",
              "MON DD YYYY", "DD-MON-YYYY", "D Mon YYYY", "DDMONYYYY", "Mon-DD-YYYY",
              "Weekday, Month D, YYYY", "Month Dth, YYYY", "Dy Mon DD, YYYY",
              "MM/DD/YYYY HH:MM", "M/D/YYYY h:MM AM", "YYYY-MM-DDTHH:MM:SS",
              "YYYY-MM-DD HH:MM", "YYYYMMDD HHMM", "MM/DD/YY@HHMM", "DD-MON-YYYY HH:MM",
              "Mon D YYYY h:MMam"]
TIMESTAMP_STYLES = [s for s in DOS_STYLES if ("HH" in s or "h:" in s)]


def fmt(d, style, t=(0, 0, 0)):
    return STYLES[style](d, t)


def all_renderings(d):
    """Every way this module can print date d (date part only, for checks)."""
    out = []
    for name, f in STYLES.items():
        s = f(d, (0, 0, 0))
        if name in TIMESTAMP_STYLES:
            s = s.split(" ")[0].split("T")[0].split("@")[0] if not name.startswith("Mon D YYYY") else " ".join(s.split(" ")[:3])
        out.append(s)
    return out
