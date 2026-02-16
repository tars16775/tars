"""
╔══════════════════════════════════════════════════════════════╗
║       TARS — Flight Engine v2.0 (10-Phase Transformation)    ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Phase 1:  Core Engine — Google Flights URL builder, parser  ║
║  Phase 2:  Booking Links — direct Google Flights link/flight ║
║  Phase 3:  Smart Sampling — 6-month range (weekly cadence)   ║
║  Phase 4:  HTML Email Templates — airline-grade design       ║
║  Phase 5:  Enhanced Excel — hyperlinks, conditional color    ║
║  Phase 6:  Price Tracker — persistent JSON DB for routes     ║
║  Phase 7:  Alert Engine — background price checks + alerts   ║
║  Phase 8:  Rich iMessage — booking links in notifications    ║
║  Phase 9:  Pipeline Integration — report + email + notify    ║
║  Phase 10: Tool Registration — brain tools + executor        ║
║                                                              ║
║  ⚠️ ONLY Google Flights. NEVER Kayak/Skyscanner/Expedia.    ║
╚══════════════════════════════════════════════════════════════╝
"""

import json
import os
import re
import threading
import time
import urllib.parse
from datetime import datetime, timedelta

from hands.cdp import CDP


class _FlightSearchTimeout(Exception):
    """Raised when flight search exceeds time limit."""
    pass


# ═══════════════════════════════════════════════════════
#  PHASE 1 — Airport Code Lookup
# ═══════════════════════════════════════════════════════

CITY_TO_IATA = {
    # ── US Major ──
    "new york": "JFK", "nyc": "JFK", "jfk": "JFK", "laguardia": "LGA", "newark": "EWR",
    "los angeles": "LAX", "la": "LAX", "lax": "LAX",
    "chicago": "ORD", "ohare": "ORD", "midway": "MDW",
    "san francisco": "SFO", "sf": "SFO",
    "miami": "MIA",
    "dallas": "DFW", "dfw": "DFW",
    "houston": "IAH", "hobby": "HOU",
    "atlanta": "ATL",
    "boston": "BOS",
    "seattle": "SEA",
    "denver": "DEN",
    "las vegas": "LAS", "vegas": "LAS",
    "orlando": "MCO",
    "tampa": "TPA",
    "phoenix": "PHX",
    "detroit": "DTW",
    "minneapolis": "MSP",
    "philadelphia": "PHL", "philly": "PHL",
    "washington": "IAD", "dc": "DCA", "dulles": "IAD", "reagan": "DCA",
    "san diego": "SAN",
    "austin": "AUS",
    "nashville": "BNA",
    "portland": "PDX",
    "charlotte": "CLT",
    "salt lake city": "SLC", "slc": "SLC",
    "pittsburgh": "PIT",
    "st louis": "STL", "saint louis": "STL",
    "honolulu": "HNL", "hawaii": "HNL",
    # ── International ──
    "london": "LHR", "heathrow": "LHR", "gatwick": "LGW",
    "paris": "CDG",
    "tokyo": "NRT", "narita": "NRT", "haneda": "HND",
    "dubai": "DXB",
    "singapore": "SIN",
    "hong kong": "HKG",
    "toronto": "YYZ",
    "vancouver": "YVR",
    "sydney": "SYD",
    "melbourne": "MEL",
    "mumbai": "BOM", "bombay": "BOM",
    "delhi": "DEL", "new delhi": "DEL",
    "bangkok": "BKK",
    "istanbul": "IST",
    "rome": "FCO",
    "madrid": "MAD",
    "barcelona": "BCN",
    "amsterdam": "AMS",
    "frankfurt": "FRA",
    "berlin": "BER",
    "munich": "MUC",
    "zurich": "ZRH",
    "cancun": "CUN",
    "mexico city": "MEX",
    "sao paulo": "GRU",
    "rio": "GIG", "rio de janeiro": "GIG",
    "cairo": "CAI",
    "doha": "DOH",
    "seoul": "ICN", "incheon": "ICN",
    "beijing": "PEK",
    "shanghai": "PVG",
    "kuala lumpur": "KUL",
    "jakarta": "CGK",
    "johannesburg": "JNB",
    "nairobi": "NBO",
    "buenos aires": "EZE",
    "bogota": "BOG",
    "lima": "LIM",
    "lisbon": "LIS",
    "dublin": "DUB",
    "edinburgh": "EDI",
    "manchester": "MAN",
    "copenhagen": "CPH",
    "stockholm": "ARN",
    "oslo": "OSL",
    "helsinki": "HEL",
    "vienna": "VIE",
    "prague": "PRG",
    "warsaw": "WAW",
    "athens": "ATH",
    "milan": "MXP",
    # ── South Asia ──
    "kathmandu": "KTM", "nepal": "KTM",
    "colombo": "CMB", "sri lanka": "CMB",
    "dhaka": "DAC", "bangladesh": "DAC",
    "islamabad": "ISB", "lahore": "LHE", "karachi": "KHI",
    "chennai": "MAA", "madras": "MAA",
    "bangalore": "BLR", "bengaluru": "BLR",
    "hyderabad": "HYD",
    "kolkata": "CCU", "calcutta": "CCU",
    "goa": "GOI",
    # ── Southeast Asia ──
    "manila": "MNL", "philippines": "MNL",
    "hanoi": "HAN", "ho chi minh": "SGN", "saigon": "SGN",
    "phnom penh": "PNH", "cambodia": "PNH",
    "bali": "DPS",
    "phuket": "HKT",
    "taipei": "TPE", "taiwan": "TPE",
    # ── Middle East / Africa ──
    "abu dhabi": "AUH",
    "riyadh": "RUH", "jeddah": "JED", "saudi": "RUH",
    "tel aviv": "TLV", "israel": "TLV",
    "amman": "AMM", "jordan": "AMM",
    "beirut": "BEY", "lebanon": "BEY",
    "addis ababa": "ADD", "ethiopia": "ADD",
    "lagos": "LOS", "nigeria": "LOS",
    "casablanca": "CMN", "morocco": "CMN",
    "cape town": "CPT",
    "dar es salaam": "DAR", "tanzania": "DAR",
    # ── Americas ──
    "havana": "HAV", "cuba": "HAV",
    "san jose": "SJC", "costa rica": "SJO",
    "panama city": "PTY", "panama": "PTY",
    "santiago": "SCL", "chile": "SCL",
    "medellin": "MDE",
    "quito": "UIO", "ecuador": "UIO",
    "montevideo": "MVD", "uruguay": "MVD",
    # ── Oceania ──
    "auckland": "AKL", "new zealand": "AKL",
    "wellington": "WLG",
    "brisbane": "BNE",
    "perth": "PER",
    "fiji": "NAN",
}


def _resolve_airport(city_or_code: str) -> str:
    """Resolve a city name or airport code to IATA code."""
    text = city_or_code.strip().lower()
    if text in CITY_TO_IATA:
        return CITY_TO_IATA[text]
    if len(text) == 3 and text.isalpha():
        return text.upper()
    for city, code in CITY_TO_IATA.items():
        if text in city or city in text:
            return code
    upper = city_or_code.strip().upper()
    if len(upper) == 3 and upper.isalpha():
        return upper
    return city_or_code.strip()


def _parse_date(date_str: str) -> str:
    """Parse a human date string into YYYY-MM-DD format."""
    if not date_str:
        return ""
    text = date_str.strip()
    if re.match(r'^\d{4}-\d{2}-\d{2}$', text):
        return text
    now = datetime.now()
    formats = [
        "%B %d, %Y", "%B %d %Y", "%B %d",
        "%b %d, %Y", "%b %d %Y", "%b %d",
        "%m/%d/%Y", "%m/%d", "%m-%d-%Y", "%Y/%m/%d",
    ]
    for fmt in formats:
        try:
            parsed = datetime.strptime(text, fmt)
            if "%Y" not in fmt and "%y" not in fmt:
                parsed = parsed.replace(year=now.year)
                if parsed < now:
                    parsed = parsed.replace(year=now.year + 1)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue
    lower = text.lower()
    if "today" in lower:
        return now.strftime("%Y-%m-%d")
    if "tomorrow" in lower:
        return (now + timedelta(days=1)).strftime("%Y-%m-%d")
    if "next week" in lower:
        return (now + timedelta(days=7)).strftime("%Y-%m-%d")
    if "next month" in lower:
        return (now + timedelta(days=30)).strftime("%Y-%m-%d")
    if "this week" in lower:
        return now.strftime("%Y-%m-%d")
    if "this month" in lower:
        return (now + timedelta(days=1)).strftime("%Y-%m-%d")
    import calendar
    for month_num in range(1, 13):
        month_name = calendar.month_name[month_num].lower()
        month_abbr = calendar.month_abbr[month_num].lower()
        if month_name in lower or month_abbr in lower:
            year = now.year
            target = datetime(year, month_num, 15)
            if target < now:
                target = target.replace(year=year + 1)
            return target.strftime("%Y-%m-%d")
    print(f"    ⚠️ Could not parse date '{text}', defaulting to tomorrow")
    return (now + timedelta(days=1)).strftime("%Y-%m-%d")


# ═══════════════════════════════════════════════════════
#  PHASE 2 — Google Flights URL Builder + Booking Links
# ═══════════════════════════════════════════════════════

def _build_google_flights_url(
    origin: str, destination: str, depart_date: str,
    return_date: str = "", passengers: int = 1,
    trip_type: str = "round_trip", cabin: str = "economy",
    stops: str = "any", sort_by: str = "price",
) -> str:
    """Construct a Google Flights search URL with all parameters encoded."""
    origin_code = _resolve_airport(origin)
    dest_code = _resolve_airport(destination)
    depart = _parse_date(depart_date)
    query_parts = [f"flights from {origin_code} to {dest_code}"]
    if depart:
        query_parts.append(f"on {depart}")
    if trip_type == "one_way":
        query_parts.append("one way")
    elif return_date:
        ret = _parse_date(return_date)
        query_parts.append(f"return {ret}")
    if cabin != "economy":
        query_parts.append(cabin.replace("_", " "))
    if stops == "nonstop":
        query_parts.append("nonstop")
    elif stops == "1stop":
        query_parts.append("1 stop or fewer")
    if passengers > 1:
        query_parts.append(f"{passengers} passengers")
    query = " ".join(query_parts)
    return f"https://www.google.com/travel/flights?q={urllib.parse.quote_plus(query)}"


def _build_booking_link(origin: str, destination: str, depart_date: str,
                        return_date: str = "", trip_type: str = "round_trip") -> str:
    """Build a clean Google Flights booking link for a specific date."""
    origin_code = _resolve_airport(origin)
    dest_code = _resolve_airport(destination)
    depart = _parse_date(depart_date) if not re.match(r'^\d{4}-\d{2}-\d{2}$', depart_date) else depart_date
    parts = [f"flights from {origin_code} to {dest_code} on {depart}"]
    if trip_type == "one_way":
        parts.append("one way")
    elif return_date:
        ret = _parse_date(return_date) if not re.match(r'^\d{4}-\d{2}-\d{2}$', return_date) else return_date
        parts.append(f"return {ret}")
    return f"https://www.google.com/travel/flights?q={urllib.parse.quote_plus(' '.join(parts))}"


# ═══════════════════════════════════════════════════════
#  PHASE 1 — Flight Data Extraction
# ═══════════════════════════════════════════════════════

def _extract_flight_data(page_text: str) -> list:
    """Parse Google Flights results text into structured flight data."""
    flights = []
    lines = page_text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        price_match = re.search(r'\$[\d,]+', line)
        if price_match:
            price = price_match.group()
            context_start = max(0, i - 15)
            context_end = min(len(lines), i + 3)
            context = "\n".join(lines[context_start:context_end])
            time_matches = re.findall(r'\d{1,2}:\d{2}\s*(?:AM|PM)', context)
            airport_matches = re.findall(r'\b([A-Z]{3})\b', context)
            airport_codes = [a for a in airport_matches if a not in (
                'THE', 'AND', 'FOR', 'NOT', 'ALL', 'NEW', 'USD', 'AVG',
                'TOP', 'SEE', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN',
            )]
            duration_match = re.search(r'(\d+\s*hr?\s*(?:\d+\s*min)?)', context)
            duration = duration_match.group(1).strip() if duration_match else ""
            airline = ""
            common_airlines = [
                "Delta", "United", "American", "Southwest", "JetBlue", "Spirit",
                "Frontier", "Alaska", "Hawaiian", "Sun Country", "Breeze",
                "Air Canada", "WestJet", "British Airways", "Lufthansa",
                "Emirates", "Qatar Airways", "Singapore Airlines", "Turkish Airlines",
                "Air France", "KLM", "Iberia", "Ryanair", "EasyJet",
                "Allegiant", "Avianca", "Copa", "Volaris", "VivaAerobus",
            ]
            for li in range(max(0, i - 12), i):
                line_text = lines[li].strip()
                for al in common_airlines:
                    if al.lower() == line_text.lower() or al.lower() in line_text.lower():
                        airline = al
                        break
                if airline:
                    break
            stops_text = "Nonstop"
            stop_match = re.search(r'(\d+)\s*stop', context, re.IGNORECASE)
            if stop_match:
                n = stop_match.group(1)
                stops_text = f"{n} stop{'s' if int(n) > 1 else ''}"
            elif "nonstop" in context.lower():
                stops_text = "Nonstop"
            flight = {
                "price": price,
                "airline": airline or "—",
                "stops": stops_text,
                "duration": duration or "—",
            }
            if len(time_matches) >= 2:
                flight["depart_time"] = time_matches[0]
                flight["arrive_time"] = time_matches[1]
            if len(airport_codes) >= 2:
                flight["from"] = airport_codes[0]
                flight["to"] = airport_codes[1]
            key = f"{price}_{airline}_{flight.get('depart_time', '')}"
            if not any(f"{f['price']}_{f['airline']}_{f.get('depart_time', '')}" == key for f in flights):
                flights.append(flight)
        i += 1

    def price_num(f):
        try:
            return int(f["price"].replace("$", "").replace(",", ""))
        except (ValueError, KeyError):
            return 99999
    flights.sort(key=price_num)
    return flights


def _price_num(price_str: str) -> int:
    """Extract numeric price from string like '$542'."""
    try:
        return int(re.sub(r'[^\d]', '', price_str))
    except (ValueError, TypeError):
        return 99999


def _format_flights(flights: list, query_desc: str) -> str:
    """Format flights into a clean, readable report."""
    if not flights:
        return f"❌ No flights found for: {query_desc}\n\nTry different dates or a nearby airport."
    lines = [f"✈️ **Flight Search Results** — {query_desc}\n"]
    lines.append(f"Found {len(flights)} options (sorted by price):\n")
    lines.append(f"{'#':<3} {'Price':<10} {'Airline':<15} {'Depart':<10} {'Arrive':<10} {'Duration':<12} {'Stops'}")
    lines.append("─" * 80)
    for i, f in enumerate(flights[:15], 1):
        lines.append(
            f"{i:<3} {f.get('price', '?'):<10} "
            f"{f.get('airline', '?'):<15} "
            f"{f.get('depart_time', '?'):<10} "
            f"{f.get('arrive_time', '?'):<10} "
            f"{f.get('duration', '?'):<12} "
            f"{f.get('stops', '?')}"
        )
    if len(flights) > 15:
        lines.append(f"\n... and {len(flights) - 15} more options")
    cheapest = flights[0]
    lines.append(f"\n💰 **Cheapest**: {cheapest.get('price', '?')} — {cheapest.get('airline', '?')} ({cheapest.get('stops', '?')}, {cheapest.get('duration', '?')})")
    nonstops = [f for f in flights if "nonstop" in f.get("stops", "").lower()]
    if nonstops:
        best_ns = nonstops[0]
        lines.append(f"✈️ **Cheapest Nonstop**: {best_ns.get('price', '?')} — {best_ns.get('airline', '?')} ({best_ns.get('duration', '?')})")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════
#  PHASE 4 — Elegant HTML Email Templates
# ═══════════════════════════════════════════════════════

def _html_flight_report_email(origin_code, dest_code, depart_date, return_date, flights, search_url):
    """Generate a beautiful HTML email for flight search results."""
    cheapest = flights[0] if flights else {}
    nonstops = [f for f in flights if "nonstop" in f.get("stops", "").lower()]
    best_nonstop = nonstops[0] if nonstops else None
    date_display = depart_date
    if return_date:
        date_display = f"{depart_date}  →  {return_date}"

    flight_rows = ""
    for i, f in enumerate(flights[:12], 1):
        bg = "#FFFFFF" if i % 2 == 1 else "#F8FAFC"
        price_color = "#059669" if i == 1 else "#1E293B"
        badge = ""
        if i == 1:
            badge = '<span style="background:#059669;color:#fff;font-size:10px;padding:2px 8px;border-radius:12px;margin-left:6px;">CHEAPEST</span>'
        elif f.get("stops", "").lower() == "nonstop" and f == (best_nonstop or {}):
            badge = '<span style="background:#2563EB;color:#fff;font-size:10px;padding:2px 8px;border-radius:12px;margin-left:6px;">BEST NONSTOP</span>'
        stops_color = "#059669" if "nonstop" in f.get("stops", "").lower() else "#64748B"
        flight_rows += f"""
        <tr style="background:{bg};">
          <td style="padding:14px 16px;border-bottom:1px solid #F1F5F9;font-weight:600;color:{price_color};font-size:16px;">{f.get('price', '—')}{badge}</td>
          <td style="padding:14px 16px;border-bottom:1px solid #F1F5F9;">
            <div style="font-weight:600;color:#1E293B;">{f.get('airline', '—')}</div>
            <div style="color:#64748B;font-size:12px;margin-top:2px;">{f.get('duration', '—')}</div>
          </td>
          <td style="padding:14px 16px;border-bottom:1px solid #F1F5F9;">
            <div style="font-weight:500;color:#1E293B;">{f.get('depart_time', '—')} → {f.get('arrive_time', '—')}</div>
          </td>
          <td style="padding:14px 16px;border-bottom:1px solid #F1F5F9;">
            <span style="color:{stops_color};font-weight:500;">{f.get('stops', '—')}</span>
          </td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#F1F5F9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <div style="max-width:640px;margin:0 auto;background:#FFFFFF;">
    <div style="background:linear-gradient(135deg,#0F172A 0%,#1E293B 100%);padding:32px 24px;text-align:center;">
      <div style="font-size:32px;margin-bottom:8px;">✈️</div>
      <h1 style="color:#FFFFFF;font-size:22px;font-weight:700;margin:0;">Flight Report</h1>
      <p style="color:#94A3B8;font-size:14px;margin:8px 0 0;">{origin_code} → {dest_code}</p>
    </div>
    <div style="margin:24px;padding:20px;background:#F8FAFC;border-radius:12px;border:1px solid #E2E8F0;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td style="text-align:center;">
            <div style="font-size:28px;font-weight:700;color:#0F172A;">{origin_code}</div>
            <div style="color:#64748B;font-size:12px;margin-top:4px;">Origin</div>
          </td>
          <td style="text-align:center;padding:0 16px;">
            <div style="color:#94A3B8;font-size:18px;">· · · ✈ · · ·</div>
          </td>
          <td style="text-align:center;">
            <div style="font-size:28px;font-weight:700;color:#0F172A;">{dest_code}</div>
            <div style="color:#64748B;font-size:12px;margin-top:4px;">Destination</div>
          </td>
        </tr>
      </table>
      <div style="text-align:center;margin-top:12px;color:#475569;font-size:14px;">📅 {date_display}</div>
    </div>
    <div style="margin:0 24px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td style="background:#F0FDF4;border-radius:8px;padding:14px;text-align:center;width:33%;">
            <div style="font-size:20px;font-weight:700;color:#059669;">{cheapest.get('price', '—')}</div>
            <div style="color:#065F46;font-size:11px;margin-top:2px;">Cheapest</div>
          </td>
          <td style="width:8px;"></td>
          <td style="background:#EFF6FF;border-radius:8px;padding:14px;text-align:center;width:33%;">
            <div style="font-size:20px;font-weight:700;color:#2563EB;">{len(flights)}</div>
            <div style="color:#1E40AF;font-size:11px;margin-top:2px;">Options</div>
          </td>
          <td style="width:8px;"></td>
          <td style="background:#FFF7ED;border-radius:8px;padding:14px;text-align:center;width:33%;">
            <div style="font-size:20px;font-weight:700;color:#EA580C;">{best_nonstop.get('price', 'N/A') if best_nonstop else 'N/A'}</div>
            <div style="color:#9A3412;font-size:11px;margin-top:2px;">Best Nonstop</div>
          </td>
        </tr>
      </table>
    </div>
    <div style="margin:24px;">
      <h2 style="font-size:16px;color:#0F172A;margin:0 0 12px;font-weight:600;">All Flights</h2>
      <table width="100%" cellpadding="0" cellspacing="0" style="border-radius:8px;overflow:hidden;border:1px solid #E2E8F0;">
        <tr style="background:#0F172A;">
          <th style="padding:12px 16px;text-align:left;color:#FFFFFF;font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Price</th>
          <th style="padding:12px 16px;text-align:left;color:#FFFFFF;font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Airline</th>
          <th style="padding:12px 16px;text-align:left;color:#FFFFFF;font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Schedule</th>
          <th style="padding:12px 16px;text-align:left;color:#FFFFFF;font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Stops</th>
        </tr>
        {flight_rows}
      </table>
      {f'<p style="color:#94A3B8;font-size:12px;margin-top:8px;text-align:center;">Showing top 12 of {len(flights)} results</p>' if len(flights) > 12 else ''}
    </div>
    <div style="margin:24px;text-align:center;">
      <a href="{search_url}" style="display:inline-block;background:#2563EB;color:#FFFFFF;text-decoration:none;padding:14px 32px;border-radius:8px;font-weight:600;font-size:14px;">View on Google Flights →</a>
    </div>
    <div style="background:#F8FAFC;padding:20px 24px;text-align:center;border-top:1px solid #E2E8F0;">
      <p style="color:#94A3B8;font-size:12px;margin:0;">Powered by TARS · {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
      <p style="color:#CBD5E1;font-size:11px;margin:4px 0 0;">Prices may change. Google Flights is the source of truth.</p>
    </div>
  </div>
</body>
</html>"""


def _html_cheapest_dates_email(origin_code, dest_code, date_results, start_date, end_date):
    """Generate a beautiful HTML email for cheapest dates comparison."""
    if not date_results:
        return "<p>No results found.</p>"
    cheapest = date_results[0]

    date_rows = ""
    for i, dr in enumerate(date_results, 1):
        bg = "#FFFFFF" if i % 2 == 1 else "#F8FAFC"
        price_color = "#059669" if i <= 3 else "#1E293B"
        badge = ""
        if i == 1:
            badge = '<span style="background:#059669;color:#fff;font-size:9px;padding:2px 6px;border-radius:10px;margin-left:4px;">🏆 BEST</span>'
        elif i == 2:
            badge = '<span style="background:#EAB308;color:#fff;font-size:9px;padding:2px 6px;border-radius:10px;margin-left:4px;">2nd</span>'
        elif i == 3:
            badge = '<span style="background:#F97316;color:#fff;font-size:9px;padding:2px 6px;border-radius:10px;margin-left:4px;">3rd</span>'
        link = dr.get("booking_link", "#")
        date_rows += f"""
        <tr style="background:{bg};">
          <td style="padding:12px 14px;border-bottom:1px solid #F1F5F9;">
            <div style="font-weight:600;color:#0F172A;">{dr['date']}</div>
            <div style="color:#94A3B8;font-size:11px;">{dr['day']}</div>
          </td>
          <td style="padding:12px 14px;border-bottom:1px solid #F1F5F9;font-weight:700;color:{price_color};font-size:15px;">{dr['price']}{badge}</td>
          <td style="padding:12px 14px;border-bottom:1px solid #F1F5F9;">
            <div style="color:#1E293B;">{dr['airline']}</div>
            <div style="color:#94A3B8;font-size:11px;">{dr['stops']} · {dr['duration']}</div>
          </td>
          <td style="padding:12px 14px;border-bottom:1px solid #F1F5F9;text-align:center;">
            <a href="{link}" style="display:inline-block;background:#EFF6FF;color:#2563EB;text-decoration:none;padding:6px 12px;border-radius:6px;font-size:12px;font-weight:500;">Book →</a>
          </td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#F1F5F9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <div style="max-width:640px;margin:0 auto;background:#FFFFFF;">
    <div style="background:linear-gradient(135deg,#0F172A 0%,#1E293B 100%);padding:32px 24px;text-align:center;">
      <div style="font-size:32px;margin-bottom:8px;">📊</div>
      <h1 style="color:#FFFFFF;font-size:22px;font-weight:700;margin:0;">Cheapest Dates Report</h1>
      <p style="color:#94A3B8;font-size:14px;margin:8px 0 0;">{origin_code} → {dest_code} · {start_date} – {end_date}</p>
    </div>
    <div style="margin:24px;padding:24px;background:linear-gradient(135deg,#F0FDF4 0%,#DCFCE7 100%);border-radius:12px;border:1px solid #BBF7D0;text-align:center;">
      <div style="font-size:12px;text-transform:uppercase;letter-spacing:1px;color:#065F46;font-weight:600;">🏆 Best Price Found</div>
      <div style="font-size:36px;font-weight:800;color:#059669;margin:8px 0;">{cheapest['price']}</div>
      <div style="color:#065F46;font-size:14px;">{cheapest['date']} ({cheapest['day']}) · {cheapest['airline']} · {cheapest['stops']}</div>
      <a href="{cheapest.get('booking_link', '#')}" style="display:inline-block;background:#059669;color:#FFFFFF;text-decoration:none;padding:10px 24px;border-radius:8px;font-weight:600;font-size:13px;margin-top:12px;">Book This Flight →</a>
    </div>
    <div style="margin:0 24px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td style="background:#F8FAFC;border-radius:8px;padding:12px;text-align:center;width:50%;">
            <div style="font-size:18px;font-weight:700;color:#2563EB;">{len(date_results)}</div>
            <div style="color:#64748B;font-size:11px;">Dates Scanned</div>
          </td>
          <td style="width:8px;"></td>
          <td style="background:#F8FAFC;border-radius:8px;padding:12px;text-align:center;width:50%;">
            <div style="font-size:18px;font-weight:700;color:#2563EB;">{len([d for d in date_results if d.get('price_num', 99999) < 99999])}</div>
            <div style="color:#64748B;font-size:11px;">With Flights</div>
          </td>
        </tr>
      </table>
    </div>
    <div style="margin:24px;">
      <h2 style="font-size:16px;color:#0F172A;margin:0 0 12px;font-weight:600;">All Dates (sorted by price)</h2>
      <table width="100%" cellpadding="0" cellspacing="0" style="border-radius:8px;overflow:hidden;border:1px solid #E2E8F0;">
        <tr style="background:#0F172A;">
          <th style="padding:10px 14px;text-align:left;color:#FFFFFF;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Date</th>
          <th style="padding:10px 14px;text-align:left;color:#FFFFFF;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Price</th>
          <th style="padding:10px 14px;text-align:left;color:#FFFFFF;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Details</th>
          <th style="padding:10px 14px;text-align:center;color:#FFFFFF;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Book</th>
        </tr>
        {date_rows}
      </table>
    </div>
    <div style="background:#F8FAFC;padding:20px 24px;text-align:center;border-top:1px solid #E2E8F0;">
      <p style="color:#94A3B8;font-size:12px;margin:0;">Powered by TARS · {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
      <p style="color:#CBD5E1;font-size:11px;margin:4px 0 0;">Prices may change. Book early for best rates.</p>
    </div>
  </div>
</body>
</html>"""


def _html_price_alert_email(origin_code, dest_code, target_price, current_price,
                            airline, depart_date, booking_link, tracker_id):
    """Generate a beautiful HTML email for price drop alerts."""
    savings = target_price - current_price if current_price < target_price else 0
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#F1F5F9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <div style="max-width:640px;margin:0 auto;background:#FFFFFF;">
    <div style="background:linear-gradient(135deg,#059669 0%,#047857 100%);padding:32px 24px;text-align:center;">
      <div style="font-size:40px;margin-bottom:8px;">🔔</div>
      <h1 style="color:#FFFFFF;font-size:24px;font-weight:700;margin:0;">Price Alert!</h1>
      <p style="color:#A7F3D0;font-size:14px;margin:8px 0 0;">Your tracked route hit your target price</p>
    </div>
    <div style="margin:24px;padding:28px;background:linear-gradient(135deg,#F0FDF4 0%,#DCFCE7 100%);border-radius:16px;border:2px solid #059669;text-align:center;">
      <div style="color:#064E3B;font-size:13px;text-transform:uppercase;letter-spacing:1px;font-weight:600;">Current Price</div>
      <div style="font-size:48px;font-weight:800;color:#059669;margin:8px 0;">${current_price}</div>
      <div style="color:#065F46;font-size:14px;margin-top:4px;">Your target: ${target_price} {'✅' if current_price <= target_price else ''}</div>
      {f'<div style="margin-top:8px;background:#059669;display:inline-block;color:#fff;padding:4px 12px;border-radius:20px;font-size:13px;font-weight:600;">You save ${savings}!</div>' if savings > 0 else ''}
    </div>
    <div style="margin:0 24px 24px;padding:20px;background:#F8FAFC;border-radius:12px;border:1px solid #E2E8F0;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td style="padding:8px 0;">
            <span style="color:#64748B;font-size:12px;">Route</span><br>
            <span style="font-weight:700;color:#0F172A;font-size:16px;">{origin_code} → {dest_code}</span>
          </td>
          <td style="padding:8px 0;text-align:right;">
            <span style="color:#64748B;font-size:12px;">Date</span><br>
            <span style="font-weight:700;color:#0F172A;font-size:16px;">{depart_date}</span>
          </td>
        </tr>
        <tr>
          <td style="padding:8px 0;">
            <span style="color:#64748B;font-size:12px;">Airline</span><br>
            <span style="font-weight:600;color:#0F172A;">{airline}</span>
          </td>
          <td style="padding:8px 0;text-align:right;">
            <span style="color:#64748B;font-size:12px;">Tracker</span><br>
            <span style="font-weight:600;color:#0F172A;">{tracker_id}</span>
          </td>
        </tr>
      </table>
    </div>
    <div style="margin:24px;text-align:center;">
      <a href="{booking_link}" style="display:inline-block;background:#059669;color:#FFFFFF;text-decoration:none;padding:16px 40px;border-radius:10px;font-weight:700;font-size:16px;letter-spacing:0.5px;">🛫 Book Now →</a>
      <p style="color:#94A3B8;font-size:12px;margin-top:12px;">Act fast — prices change frequently!</p>
    </div>
    <div style="background:#F8FAFC;padding:20px 24px;text-align:center;border-top:1px solid #E2E8F0;">
      <p style="color:#94A3B8;font-size:12px;margin:0;">Powered by TARS Flight Tracker · {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
    </div>
  </div>
</body>
</html>"""


# ═══════════════════════════════════════════════════════
#  PHASE 1 — Main Flight Search Function
# ═══════════════════════════════════════════════════════

def search_flights(
    origin: str, destination: str, depart_date: str,
    return_date: str = "", passengers: int = 1,
    trip_type: str = "round_trip", cabin: str = "economy",
    stops: str = "any", sort_by: str = "price", max_price: int = 0,
) -> dict:
    """Search for flights using Google Flights (URL-parameter approach)."""
    try:
        origin_code = _resolve_airport(origin)
        dest_code = _resolve_airport(destination)
        depart = _parse_date(depart_date)
        if trip_type == "one_way":
            return_date = ""
        query_desc = f"{origin_code} → {dest_code} on {depart}"
        if return_date:
            ret = _parse_date(return_date)
            query_desc += f", returning {ret}"
        if stops != "any":
            query_desc += f" ({stops})"
        if cabin != "economy":
            query_desc += f" [{cabin}]"
        url = _build_google_flights_url(
            origin=origin, destination=destination,
            depart_date=depart_date, return_date=return_date,
            passengers=passengers, trip_type=trip_type,
            cabin=cabin, stops=stops, sort_by=sort_by,
        )
        deadline = time.time() + 45
        cdp = None
        try:
            cdp = CDP()
            cdp.ensure_connected()
            cdp.send("Page.navigate", {"url": url})
            time.sleep(6)
            if time.time() > deadline:
                raise _FlightSearchTimeout("Flight search timed out")
            page_text = ""
            for attempt in range(5):
                if time.time() > deadline:
                    raise _FlightSearchTimeout("Flight search timed out")
                r = cdp.send("Runtime.evaluate", {
                    "expression": "document.body.innerText.substring(0, 15000)",
                    "returnByValue": True,
                })
                page_text = r.get("result", {}).get("value", "")
                if "$" in page_text and ("stop" in page_text.lower() or "nonstop" in page_text.lower()):
                    break
                time.sleep(2)
            if time.time() > deadline:
                raise _FlightSearchTimeout("Flight search timed out")
            r2 = cdp.send("Runtime.evaluate", {
                "expression": """
                    (function() {
                        let results = [];
                        document.querySelectorAll('li, [role="listitem"], [data-resultid]').forEach(el => {
                            let t = el.innerText.trim();
                            if (t.includes('$') && t.length > 20 && t.length < 500) {
                                results.push(t);
                            }
                        });
                        if (results.length === 0) {
                            let main = document.querySelector('[role="main"]') || document.body;
                            return main.innerText.substring(0, 20000);
                        }
                        return results.join('\\n---\\n');
                    })()
                """,
                "returnByValue": True,
            })
            extended_text = r2.get("result", {}).get("value", "")
            combined_text = page_text + "\n" + (extended_text or "")
        except _FlightSearchTimeout:
            if cdp:
                try: cdp.close()
                except: pass
            return {"success": False, "content": "❌ Flight search timed out.", "flights": []}
        finally:
            if cdp:
                try: cdp.close()
                except: pass
        flights = _extract_flight_data(combined_text)
        if max_price > 0:
            flights = [f for f in flights if _price_num(f.get("price", "$99999")) <= max_price]
        for f in flights:
            f["booking_link"] = url
        report = _format_flights(flights, query_desc)
        return {"success": True, "content": report, "flights": flights, "url": url, "source": "Google Flights"}
    except Exception as e:
        return {"success": False, "content": f"❌ Flight search failed: {str(e)}", "flights": [], "error": str(e)}


# ═══════════════════════════════════════════════════════
#  PHASE 5 — Enhanced Excel with Hyperlinks
# ═══════════════════════════════════════════════════════

def _generate_flight_excel(title, flights, origin_code, dest_code, search_url, summary_data=None):
    """Generate a professional Excel report with hyperlinks and conditional formatting."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        return {"success": False, "content": "openpyxl not installed"}

    REPORT_DIR = os.path.expanduser("~/Documents/TARS_Reports")
    os.makedirs(REPORT_DIR, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "Flights"

    DARK, GREEN, BLUE, GRAY = "0F172A", "059669", "2563EB", "64748B"
    ALT_ROW, WHITE = "F1F5F9", "FFFFFF"
    header_font = Font(name="Helvetica Neue", size=11, bold=True, color=WHITE)
    header_fill = PatternFill(start_color=DARK, end_color=DARK, fill_type="solid")
    data_font = Font(name="Helvetica Neue", size=10)
    link_font = Font(name="Helvetica Neue", size=10, color=BLUE, underline="single")
    alt_fill = PatternFill(start_color=ALT_ROW, end_color=ALT_ROW, fill_type="solid")
    thin_border = Border(
        left=Side(style="thin", color="E2E8F0"), right=Side(style="thin", color="E2E8F0"),
        top=Side(style="thin", color="E2E8F0"), bottom=Side(style="thin", color="E2E8F0"),
    )

    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=8)
    ws.cell(row=1, column=1, value=f"✈️ {title}").font = Font(name="Helvetica Neue", size=18, bold=True, color=DARK)
    ws.row_dimensions[1].height = 40
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=8)
    ws.cell(row=2, column=1, value=f"Generated by TARS · {datetime.now().strftime('%B %d, %Y at %I:%M %p')}").font = Font(
        name="Helvetica Neue", size=9, italic=True, color=GRAY)

    headers = ["#", "Price", "Airline", "Departure", "Arrival", "Duration", "Stops", "Book"]
    start_row = 4
    for col_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=start_row, column=col_idx, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border
    ws.row_dimensions[start_row].height = 30

    for row_idx, f in enumerate(flights[:20], start_row + 1):
        i = row_idx - start_row
        values = [i, f.get("price", "—"), f.get("airline", "—"), f.get("depart_time", "—"),
                  f.get("arrive_time", "—"), f.get("duration", "—"), f.get("stops", "—"), ""]
        for col_idx, val in enumerate(values, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.font = data_font
            cell.border = thin_border
            cell.alignment = Alignment(vertical="center")
            if i % 2 == 0:
                cell.fill = alt_fill
            if col_idx == 2:
                cell.font = Font(name="Helvetica Neue", size=11, bold=True, color=GREEN) if i == 1 else Font(name="Helvetica Neue", size=10, bold=True)
        link_cell = ws.cell(row=row_idx, column=8, value="View →")
        link_cell.hyperlink = f.get("booking_link", search_url)
        link_cell.font = link_font
        link_cell.alignment = Alignment(horizontal="center", vertical="center")
        link_cell.border = thin_border

    if summary_data:
        srow = start_row + len(flights[:20]) + 2
        ws.cell(row=srow, column=1, value="Summary").font = Font(name="Helvetica Neue", size=13, bold=True, color=DARK)
        for i, (k, v) in enumerate(summary_data.items()):
            ws.cell(row=srow + 1 + i, column=1, value=k).font = Font(name="Helvetica Neue", size=10, bold=True)
            ws.cell(row=srow + 1 + i, column=2, value=v).font = data_font

    widths = [5, 10, 18, 12, 12, 14, 12, 10]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in title)
    filename = f"{safe_title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    filepath = os.path.join(REPORT_DIR, filename)
    wb.save(filepath)
    return {"success": True, "path": filepath}


def _generate_dates_excel(origin_code, dest_code, date_results, start, end):
    """Generate an enhanced Excel report for cheapest dates with booking links."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        return {"success": False, "content": "openpyxl not installed"}

    REPORT_DIR = os.path.expanduser("~/Documents/TARS_Reports")
    os.makedirs(REPORT_DIR, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "Cheapest Dates"

    DARK, GREEN, BLUE, GRAY = "0F172A", "059669", "2563EB", "64748B"
    ALT_ROW, WHITE = "F1F5F9", "FFFFFF"
    header_font = Font(name="Helvetica Neue", size=11, bold=True, color=WHITE)
    header_fill = PatternFill(start_color=DARK, end_color=DARK, fill_type="solid")
    data_font = Font(name="Helvetica Neue", size=10)
    link_font = Font(name="Helvetica Neue", size=10, color=BLUE, underline="single")
    gold_fill = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")
    alt_fill = PatternFill(start_color=ALT_ROW, end_color=ALT_ROW, fill_type="solid")
    thin_border = Border(
        left=Side(style="thin", color="E2E8F0"), right=Side(style="thin", color="E2E8F0"),
        top=Side(style="thin", color="E2E8F0"), bottom=Side(style="thin", color="E2E8F0"),
    )

    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=9)
    ws.cell(row=1, column=1, value=f"📊 Cheapest Dates: {origin_code} → {dest_code}").font = Font(
        name="Helvetica Neue", size=18, bold=True, color=DARK)
    ws.row_dimensions[1].height = 40
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=9)
    ws.cell(row=2, column=1, value=f"Range: {start.strftime('%b %d')} – {end.strftime('%b %d, %Y')} · Generated by TARS · {datetime.now().strftime('%B %d, %Y')}").font = Font(
        name="Helvetica Neue", size=9, italic=True, color=GRAY)

    headers = ["Date", "Day", "Price", "Airline", "Departure", "Duration", "Stops", "Options", "Book"]
    start_row = 4
    for col_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=start_row, column=col_idx, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border

    for row_idx, dr in enumerate(date_results, start_row + 1):
        i = row_idx - start_row
        values = [dr["date"], dr["day"], dr["price"], dr["airline"],
                  dr["depart_time"], dr["duration"], dr["stops"], dr["options"], ""]
        for col_idx, val in enumerate(values, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.font = data_font
            cell.border = thin_border
            cell.alignment = Alignment(vertical="center")
            if i == 1:
                cell.fill = gold_fill
            elif i % 2 == 0:
                cell.fill = alt_fill
            if col_idx == 3:
                cell.font = Font(name="Helvetica Neue", size=10, bold=True, color=GREEN if i <= 3 else DARK)
        link_cell = ws.cell(row=row_idx, column=9, value="Book →")
        link_cell.hyperlink = dr.get("booking_link", "")
        link_cell.font = link_font
        link_cell.alignment = Alignment(horizontal="center", vertical="center")
        link_cell.border = thin_border

    srow = start_row + len(date_results) + 2
    ws.cell(row=srow, column=1, value="Summary").font = Font(name="Helvetica Neue", size=13, bold=True, color=DARK)
    cheapest = date_results[0]
    summary = {
        "Route": f"{origin_code} → {dest_code}",
        "Dates Scanned": str(len(date_results)),
        "Cheapest Date": f"{cheapest['date']} ({cheapest['day']})",
        "Cheapest Price": f"{cheapest['price']} — {cheapest['airline']}",
        "Source": "Google Flights",
    }
    for i, (k, v) in enumerate(summary.items()):
        ws.cell(row=srow + 1 + i, column=1, value=k).font = Font(name="Helvetica Neue", size=10, bold=True)
        ws.cell(row=srow + 1 + i, column=2, value=v).font = data_font

    widths = [12, 12, 10, 18, 12, 14, 12, 8, 10]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    safe = f"Cheapest_Dates_{origin_code}_{dest_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    filepath = os.path.join(REPORT_DIR, safe)
    wb.save(filepath)
    return {"success": True, "path": filepath}


# ═══════════════════════════════════════════════════════
#  PHASE 6 — Send HTML Email via Mail.app
# ═══════════════════════════════════════════════════════

def _send_html_email(to_address, subject, html_body, attachment_path="", from_address="tarsitgroup@outlook.com"):
    """Send an HTML email via Mail.app with optional attachment."""
    import subprocess
    import tempfile

    html_file = tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False)
    html_file.write(html_body)
    html_file.close()

    safe_subject = subject.replace('\\', '\\\\').replace('"', '\\"')

    if attachment_path and os.path.isfile(attachment_path):
        script = f'''
        set htmlContent to read POSIX file "{html_file.name}" as «class utf8»
        tell application "Mail"
            set msg to make new outgoing message with properties {{subject:"{safe_subject}", content:htmlContent, visible:false}}
            tell msg
                make new to recipient at end of to recipients with properties {{address:"{to_address}"}}
                set theAttachment to POSIX file "{attachment_path}"
                make new attachment with properties {{file name:theAttachment}} at after last paragraph
            end tell
            send msg
        end tell
        '''
    else:
        script = f'''
        set htmlContent to read POSIX file "{html_file.name}" as «class utf8»
        tell application "Mail"
            set msg to make new outgoing message with properties {{subject:"{safe_subject}", content:htmlContent, visible:false}}
            tell msg
                make new to recipient at end of to recipients with properties {{address:"{to_address}"}}
            end tell
            send msg
        end tell
        '''

    try:
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=60)
        os.unlink(html_file.name)
        if result.returncode == 0:
            return {"success": True, "content": f"HTML email sent to {to_address}: {subject}"}
        else:
            return {"success": False, "content": f"Mail.app error: {result.stderr}"}
    except Exception as e:
        try: os.unlink(html_file.name)
        except: pass
        return {"success": False, "content": f"Email failed: {e}"}


# ═══════════════════════════════════════════════════════
#  PHASE 9 — Flight Report Pipeline
# ═══════════════════════════════════════════════════════

def search_flights_report(
    origin: str, destination: str, depart_date: str,
    return_date: str = "", passengers: int = 1,
    trip_type: str = "round_trip", cabin: str = "economy",
    stops: str = "any", sort_by: str = "price",
    max_price: int = 0, email_to: str = "",
) -> dict:
    """Search flights → elegant Excel → HTML email → iMessage notification."""
    result = search_flights(
        origin=origin, destination=destination, depart_date=depart_date,
        return_date=return_date, passengers=passengers, trip_type=trip_type,
        cabin=cabin, stops=stops, sort_by=sort_by, max_price=max_price,
    )
    flights = result.get("flights", [])
    if not result.get("success") or not flights:
        return result

    origin_code = _resolve_airport(origin)
    dest_code = _resolve_airport(destination)
    depart = _parse_date(depart_date)
    ret_parsed = _parse_date(return_date) if return_date else ""
    search_url = result.get("url", "")
    cheapest = flights[0]
    nonstops = [f for f in flights if "nonstop" in f.get("stops", "").lower()]
    best_ns = nonstops[0] if nonstops else None

    summary = {
        "Route": f"{origin_code} → {dest_code}", "Departure": depart,
        "Return": ret_parsed or "One-way", "Total Options": str(len(flights)),
        "Cheapest": f"{cheapest.get('price', '?')} — {cheapest.get('airline', '?')} ({cheapest.get('stops', '?')})",
    }
    if best_ns:
        summary["Cheapest Nonstop"] = f"{best_ns.get('price', '?')} — {best_ns.get('airline', '?')}"
    summary["Search Date"] = datetime.now().strftime("%B %d, %Y")
    summary["Source"] = "Google Flights"

    title = f"Flights {origin_code}→{dest_code} {depart}"
    excel_result = _generate_flight_excel(title, flights, origin_code, dest_code, search_url, summary)
    excel_path = excel_result.get("path", "")

    emailed = False
    email_msg = ""
    if email_to:
        try:
            html = _html_flight_report_email(origin_code, dest_code, depart, ret_parsed, flights, search_url)
            mail_result = _send_html_email(
                to_address=email_to,
                subject=f"✈️ {origin_code}→{dest_code} Flight Report · {cheapest.get('price', '')} cheapest",
                html_body=html, attachment_path=excel_path,
            )
            if mail_result.get("success"):
                emailed = True
                email_msg = f"\n📧 Report emailed to {email_to}"
            else:
                email_msg = f"\n⚠️ Email failed: {mail_result.get('content', '')}"
        except Exception as e:
            email_msg = f"\n⚠️ Email failed: {e}"

    content = result["content"] + f"\n\n📊 Excel saved: {excel_path}{email_msg}"

    try:
        from voice.imessage_send import IMessageSender
        sender = IMessageSender()
        nonstop_line = ""
        if nonstops:
            nonstop_line = f"\n✈️ Best nonstop: {best_ns.get('price', '?')} — {best_ns.get('airline', '?')} ({best_ns.get('duration', '?')})"
        imsg = (
            f"✅ Flight report ready!\n\n"
            f"🛫 {origin_code} → {dest_code}\n"
            f"📅 {depart}" + (f" → {ret_parsed}" if ret_parsed else "") + "\n"
            f"📊 Found {len(flights)} options\n"
            f"💰 Cheapest: {cheapest.get('price', '?')} — {cheapest.get('airline', '?')} ({cheapest.get('stops', '?')})"
            f"{nonstop_line}\n\n"
            f"🔗 View flights: {search_url}"
        )
        if emailed:
            imsg += f"\n📧 Report emailed to {email_to}"
        sender.send(imsg)
    except Exception:
        pass

    return {"success": True, "content": content, "flights": flights,
            "excel_path": excel_path, "emailed": emailed, "url": search_url}


# ═══════════════════════════════════════════════════════
#  PHASE 3 — Cheapest Dates (Smart 6-Month Sampling)
# ═══════════════════════════════════════════════════════

def find_cheapest_dates(
    origin: str, destination: str, start_date: str,
    end_date: str = "", trip_type: str = "one_way",
    cabin: str = "economy", stops: str = "any", email_to: str = "",
) -> dict:
    """Find the cheapest day to fly within a date range (up to 6 months).

    Smart sampling:
      ≤14 days  → every day       (~14 searches)
      ≤30 days  → every 2 days    (~15 searches)
      ≤90 days  → every 5 days    (~18 searches)
      ≤180 days → every 7 days    (~26 searches)
      >180 days → every 10 days   (~25 searches)
    """
    origin_code = _resolve_airport(origin)
    dest_code = _resolve_airport(destination)

    start = datetime.strptime(_parse_date(start_date), "%Y-%m-%d")
    if end_date:
        end = datetime.strptime(_parse_date(end_date), "%Y-%m-%d")
    else:
        end = start + timedelta(days=30)

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if start < today:
        start = today + timedelta(days=1)

    total_days = (end - start).days
    if total_days <= 0:
        return {"success": False, "content": "❌ end_date must be after start_date", "dates": []}

    if total_days <= 14:
        step = 1
    elif total_days <= 30:
        step = 2
    elif total_days <= 90:
        step = 5
    elif total_days <= 180:
        step = 7
    else:
        step = 10

    dates_to_search = []
    d = start
    while d <= end:
        dates_to_search.append(d)
        d += timedelta(days=step)
    if dates_to_search[-1] != end:
        dates_to_search.append(end)

    print(f"    ✈️ Scanning {len(dates_to_search)} dates: {origin_code}→{dest_code} ({start.strftime('%b %d')} – {end.strftime('%b %d, %Y')})")

    date_results = []
    for dt in dates_to_search:
        date_str = dt.strftime("%Y-%m-%d")
        print(f"      📅 {date_str}...", end=" ", flush=True)
        try:
            r = search_flights(
                origin=origin, destination=destination,
                depart_date=date_str, trip_type=trip_type,
                cabin=cabin, stops=stops,
            )
            flights = r.get("flights", [])
            booking_link = _build_booking_link(origin, destination, date_str, trip_type=trip_type)
            if flights:
                best = flights[0]
                price = _price_num(best.get("price", "$99999"))
                date_results.append({
                    "date": date_str, "day": dt.strftime("%A"),
                    "price": best.get("price", "—"), "price_num": price,
                    "airline": best.get("airline", "—"), "stops": best.get("stops", "—"),
                    "duration": best.get("duration", "—"), "depart_time": best.get("depart_time", "—"),
                    "options": len(flights), "booking_link": booking_link,
                })
                print(f"{best.get('price', '?')} ({best.get('airline', '?')})")
            else:
                date_results.append({
                    "date": date_str, "day": dt.strftime("%A"),
                    "price": "N/A", "price_num": 99999, "airline": "—", "stops": "—",
                    "duration": "—", "depart_time": "—", "options": 0, "booking_link": booking_link,
                })
                print("no results")
        except Exception as e:
            print(f"error: {e}")
            date_results.append({
                "date": date_str, "day": dt.strftime("%A"),
                "price": "Error", "price_num": 99999, "airline": "—", "stops": "—",
                "duration": "—", "depart_time": "—", "options": 0,
                "booking_link": _build_booking_link(origin, destination, date_str, trip_type=trip_type),
            })

    if not date_results:
        return {"success": False, "content": "❌ No results for any date in range", "dates": []}

    date_results.sort(key=lambda x: x["price_num"])
    cheapest = date_results[0]

    report_lines = [
        f"✈️ **Cheapest Dates: {origin_code} → {dest_code}**",
        f"📅 Range: {start.strftime('%b %d')} – {end.strftime('%b %d, %Y')}",
        f"Scanned {len(date_results)} dates\n",
        f"{'Date':<14} {'Day':<10} {'Price':<10} {'Airline':<15} {'Stops':<10} {'Duration'}",
        "─" * 75,
    ]
    for dr in date_results:
        report_lines.append(
            f"{dr['date']:<14} {dr['day']:<10} {dr['price']:<10} "
            f"{dr['airline']:<15} {dr['stops']:<10} {dr['duration']}"
        )
    report_lines.append(f"\n🏆 **CHEAPEST**: {cheapest['date']} ({cheapest['day']}) — "
                        f"{cheapest['price']} on {cheapest['airline']} "
                        f"({cheapest['stops']}, {cheapest['duration']})")
    if len(date_results) >= 3:
        report_lines.append("\n💡 Top 3 cheapest dates:")
        for i, dr in enumerate(date_results[:3], 1):
            report_lines.append(f"  {i}. {dr['date']} ({dr['day']}) — {dr['price']} ({dr['airline']}) — {dr.get('booking_link', '')}")
    report = "\n".join(report_lines)

    excel_result = _generate_dates_excel(origin_code, dest_code, date_results, start, end)
    excel_path = excel_result.get("path", "")
    if excel_path:
        report += f"\n\n📊 Excel saved: {excel_path}"

    emailed = False
    if email_to and excel_path:
        try:
            html = _html_cheapest_dates_email(
                origin_code, dest_code, date_results,
                start.strftime('%b %d'), end.strftime('%b %d, %Y'),
            )
            mail_result = _send_html_email(
                to_address=email_to,
                subject=f"📊 Cheapest Dates: {origin_code}→{dest_code} · {cheapest['price']} lowest",
                html_body=html, attachment_path=excel_path,
            )
            if mail_result.get("success"):
                emailed = True
                report += f"\n📧 Report emailed to {email_to}"
            else:
                report += f"\n⚠️ Email failed: {mail_result.get('content', '')}"
        except Exception as e:
            report += f"\n⚠️ Email failed: {e}"

    try:
        from voice.imessage_send import IMessageSender
        sender = IMessageSender()
        imsg = (
            f"✅ Cheapest dates report ready!\n\n"
            f"🛫 {origin_code} → {dest_code}\n"
            f"📅 {start.strftime('%b %d')} – {end.strftime('%b %d, %Y')}\n"
            f"📊 Scanned {len(date_results)} dates\n\n"
            f"🏆 Cheapest: {cheapest['date']} ({cheapest['day']}) — "
            f"{cheapest['price']} on {cheapest['airline']}"
        )
        if len(date_results) >= 3:
            imsg += "\n\n💡 Top 3:"
            for i, dr in enumerate(date_results[:3], 1):
                imsg += f"\n  {i}. {dr['date']} — {dr['price']} ({dr['airline']})"
        imsg += f"\n\n🔗 Book cheapest: {cheapest.get('booking_link', '')}"
        if emailed:
            imsg += f"\n📧 Full report emailed to {email_to}"
        sender.send(imsg)
    except Exception:
        pass

    return {"success": True, "content": report, "dates": date_results,
            "cheapest": cheapest, "excel_path": excel_path, "emailed": emailed}


# ═══════════════════════════════════════════════════════
#  PHASE 6 & 7 — Price Tracker + Alert Engine
# ═══════════════════════════════════════════════════════

TRACKER_DB = os.path.expanduser("~/Documents/TARS_Reports/flight_trackers.json")


def _load_trackers():
    if os.path.isfile(TRACKER_DB):
        try:
            with open(TRACKER_DB, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def _save_trackers(trackers):
    os.makedirs(os.path.dirname(TRACKER_DB), exist_ok=True)
    with open(TRACKER_DB, "w") as f:
        json.dump(trackers, f, indent=2)


def track_flight_price(
    origin: str, destination: str, depart_date: str,
    target_price: int, return_date: str = "",
    trip_type: str = "round_trip", cabin: str = "economy",
    stops: str = "any", email_to: str = "tarsitgroup@outlook.com",
    check_interval_hours: int = 6,
) -> dict:
    """Set up a price tracker for a specific route.

    Monitors price on Google Flights at regular intervals.
    When price drops to or below target, sends:
      - Beautiful HTML email alert with booking link
      - iMessage notification
    """
    origin_code = _resolve_airport(origin)
    dest_code = _resolve_airport(destination)
    depart = _parse_date(depart_date)
    ret = _parse_date(return_date) if return_date else ""

    tracker_id = f"{origin_code}-{dest_code}-{depart[:10].replace('-', '')}"

    print(f"    🎯 Setting up tracker: {origin_code}→{dest_code} on {depart}, target ${target_price}")
    initial = search_flights(
        origin=origin, destination=destination, depart_date=depart_date,
        return_date=return_date, trip_type=trip_type, cabin=cabin, stops=stops,
    )

    current_price = None
    current_airline = "—"
    if initial.get("flights"):
        best = initial["flights"][0]
        current_price = _price_num(best.get("price", "$99999"))
        current_airline = best.get("airline", "—")

    tracker = {
        "id": tracker_id, "origin": origin_code, "destination": dest_code,
        "depart_date": depart, "return_date": ret,
        "trip_type": trip_type, "cabin": cabin, "stops": stops,
        "target_price": target_price, "email_to": email_to,
        "check_interval_hours": check_interval_hours,
        "created_at": datetime.now().isoformat(),
        "last_checked": datetime.now().isoformat(),
        "last_price": current_price, "last_airline": current_airline,
        "price_history": [{"timestamp": datetime.now().isoformat(), "price": current_price, "airline": current_airline}] if current_price else [],
        "alerts_sent": 0, "active": True,
    }

    trackers = _load_trackers()
    trackers = [t for t in trackers if t["id"] != tracker_id]
    trackers.append(tracker)
    _save_trackers(trackers)

    already_hit = current_price and current_price <= target_price
    if already_hit:
        booking_link = _build_booking_link(origin, destination, depart_date, return_date, trip_type)
        _send_price_alert(tracker, current_price, current_airline, booking_link)
        content = (
            f"🎯 Tracker set: {origin_code}→{dest_code} on {depart}\n"
            f"🔔 **ALERT: Already at target!** Current ${current_price} ≤ target ${target_price}\n"
            f"📧 Alert email sent immediately!\n"
            f"🔗 Book: {booking_link}"
        )
    else:
        content = (
            f"🎯 Tracker set: {origin_code}→{dest_code} on {depart}\n"
            f"💰 Target: ${target_price}\n"
            f"📊 Current price: ${current_price or 'unknown'} ({current_airline})\n"
            f"⏰ Checking every {check_interval_hours} hours\n"
            f"📧 Alert will be sent to {email_to}\n"
            f"🆔 Tracker ID: {tracker_id}"
        )

    try:
        from voice.imessage_send import IMessageSender
        sender = IMessageSender()
        imsg = (
            f"🎯 Flight price tracker activated!\n\n"
            f"🛫 {origin_code} → {dest_code}\n"
            f"📅 {depart}\n"
            f"💰 Target: ${target_price}\n"
            f"📊 Current: ${current_price or '?'} ({current_airline})\n"
            f"⏰ Checking every {check_interval_hours}h\n"
            f"🆔 {tracker_id}"
        )
        if already_hit:
            imsg += f"\n\n🔔 ALREADY AT TARGET! Check your email!"
        sender.send(imsg)
    except Exception:
        pass

    return {"success": True, "tracker_id": tracker_id, "content": content,
            "current_price": current_price, "target_price": target_price,
            "already_at_target": already_hit}


def get_tracked_flights() -> dict:
    """Get all active flight price trackers with their status."""
    trackers = _load_trackers()
    active = [t for t in trackers if t.get("active")]
    if not active:
        return {"success": True, "content": "📭 No active flight trackers.\n\nSet one up with track_flight_price.", "trackers": []}

    lines = ["🎯 **Active Flight Price Trackers**\n"]
    lines.append(f"{'ID':<25} {'Route':<12} {'Date':<12} {'Target':<10} {'Last Price':<12} {'Status'}")
    lines.append("─" * 85)

    for t in active:
        route = f"{t['origin']}→{t['destination']}"
        last = t.get("last_price")
        target = t["target_price"]
        status = "✅ At target!" if (last and last <= target) else "⏳ Monitoring"
        lines.append(f"{t['id']:<25} {route:<12} {t['depart_date']:<12} ${target:<9} {'$' + str(last) if last else 'N/A':<11} {status}")
        if t.get("price_history"):
            prices = [p["price"] for p in t["price_history"] if p.get("price")]
            if len(prices) >= 2:
                trend = "📈" if prices[-1] > prices[-2] else "📉" if prices[-1] < prices[-2] else "➡️"
                lines.append(f"  {trend} Price trend: {', '.join(f'${p}' for p in prices[-5:])}")

    lines.append(f"\n📊 Total active trackers: {len(active)}")
    return {"success": True, "content": "\n".join(lines), "trackers": active}


def stop_tracking(tracker_id: str) -> dict:
    """Stop a specific flight price tracker."""
    trackers = _load_trackers()
    found = False
    for t in trackers:
        if t["id"] == tracker_id:
            t["active"] = False
            found = True
            break
    if found:
        _save_trackers(trackers)
        return {"success": True, "content": f"🛑 Tracker {tracker_id} stopped."}
    return {"success": False, "content": f"❌ Tracker {tracker_id} not found."}


def _send_price_alert(tracker, current_price, airline, booking_link):
    """Send a price alert via HTML email and iMessage."""
    origin, dest = tracker["origin"], tracker["destination"]
    target, depart = tracker["target_price"], tracker["depart_date"]
    email_to = tracker.get("email_to", "tarsitgroup@outlook.com")
    tracker_id = tracker["id"]

    try:
        html = _html_price_alert_email(origin, dest, target, current_price, airline, depart, booking_link, tracker_id)
        _send_html_email(to_address=email_to, subject=f"🔔 Price Alert: {origin}→{dest} dropped to ${current_price}!", html_body=html)
    except Exception as e:
        print(f"    ⚠️ Alert email failed: {e}")

    try:
        from voice.imessage_send import IMessageSender
        sender = IMessageSender()
        savings = target - current_price if current_price < target else 0
        imsg = (
            f"🔔 PRICE ALERT!\n\n"
            f"🛫 {origin} → {dest}\n📅 {depart}\n"
            f"💰 Now: ${current_price} (target was ${target})\n✈️ {airline}"
        )
        if savings > 0:
            imsg += f"\n💚 You save ${savings}!"
        imsg += f"\n\n🔗 Book now: {booking_link}"
        sender.send(imsg)
    except Exception:
        pass


def check_price_trackers() -> dict:
    """Check all active trackers and send alerts for any that hit target.
    Called by the TARS scheduler (background thread).
    """
    trackers = _load_trackers()
    active = [t for t in trackers if t.get("active")]
    if not active:
        return {"checked": 0, "alerts": 0}

    now = datetime.now()
    checked = 0
    alerts = 0

    for tracker in active:
        last_checked = datetime.fromisoformat(tracker.get("last_checked", "2000-01-01"))
        interval = timedelta(hours=tracker.get("check_interval_hours", 6))
        if now - last_checked < interval:
            continue

        try:
            depart = datetime.strptime(tracker["depart_date"], "%Y-%m-%d")
            if depart < now:
                tracker["active"] = False
                continue
        except ValueError:
            pass

        print(f"    🔍 Checking tracker: {tracker['id']}...")
        checked += 1

        result = search_flights(
            origin=tracker["origin"], destination=tracker["destination"],
            depart_date=tracker["depart_date"], return_date=tracker.get("return_date", ""),
            trip_type=tracker.get("trip_type", "round_trip"),
            cabin=tracker.get("cabin", "economy"), stops=tracker.get("stops", "any"),
        )

        tracker["last_checked"] = now.isoformat()

        if result.get("flights"):
            best = result["flights"][0]
            price = _price_num(best.get("price", "$99999"))
            airline = best.get("airline", "—")
            tracker["last_price"] = price
            tracker["last_airline"] = airline
            tracker["price_history"].append({"timestamp": now.isoformat(), "price": price, "airline": airline})
            tracker["price_history"] = tracker["price_history"][-50:]

            if price <= tracker["target_price"]:
                booking_link = _build_booking_link(
                    tracker["origin"], tracker["destination"],
                    tracker["depart_date"], tracker.get("return_date", ""),
                    tracker.get("trip_type", "round_trip"),
                )
                _send_price_alert(tracker, price, airline, booking_link)
                tracker["alerts_sent"] = tracker.get("alerts_sent", 0) + 1
                alerts += 1
                print(f"    🔔 ALERT: {tracker['id']} at ${price} (target ${tracker['target_price']})")
            else:
                print(f"    📊 {tracker['id']}: ${price} (target ${tracker['target_price']})")

    _save_trackers(trackers)
    return {"checked": checked, "alerts": alerts}


# ═══════════════════════════════════════════════════════
#  PHASE 7 — Background Scheduler Thread
# ═══════════════════════════════════════════════════════

_scheduler_thread = None
_scheduler_running = False


def start_price_tracker_scheduler(check_interval_minutes: int = 30):
    """Start the background scheduler that checks price trackers."""
    global _scheduler_thread, _scheduler_running
    if _scheduler_running:
        return
    _scheduler_running = True

    def _scheduler_loop():
        global _scheduler_running
        print(f"    ⏰ Price tracker scheduler started (every {check_interval_minutes}min)")
        while _scheduler_running:
            try:
                result = check_price_trackers()
                if result["checked"] > 0:
                    print(f"    ⏰ Tracker check: {result['checked']} checked, {result['alerts']} alerts")
            except Exception as e:
                print(f"    ⚠️ Tracker scheduler error: {e}")
            for _ in range(check_interval_minutes * 6):
                if not _scheduler_running:
                    break
                time.sleep(10)
        print("    ⏰ Price tracker scheduler stopped")

    _scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True)
    _scheduler_thread.start()


def stop_price_tracker_scheduler():
    """Stop the background scheduler."""
    global _scheduler_running
    _scheduler_running = False
