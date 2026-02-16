"""
╔══════════════════════════════════════════════════════════════╗
║       TARS — Flight Search Engine (API-First Approach)       ║
╠══════════════════════════════════════════════════════════════╣
║  Searches flights WITHOUT fighting website UIs.              ║
║                                                              ║
║  Strategy: Google Flights URL → navigate + read (no API key)║
║                                                              ║
║  Google Flights encodes ALL search parameters in the URL.    ║
║  We construct the URL with filters baked in, navigate there, ║
║  and just READ results.                                      ║
║  No clicking, no dropdowns, no sliders, no bot detection.    ║
║                                                              ║
║  ⚠️ NEVER use Kayak, Skyscanner, Expedia — they detect bots ║
║  and serve CAPTCHAs. Google Flights is the only reliable     ║
║  source for automated flight search.                         ║
╚══════════════════════════════════════════════════════════════╝
"""

import json
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
#  Airport Code Lookup
# ═══════════════════════════════════════════════════════

# Common cities → IATA codes (covers ~90% of user queries)
CITY_TO_IATA = {
    # US Major
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

    # International
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

    # South Asia
    "kathmandu": "KTM", "nepal": "KTM",
    "colombo": "CMB", "sri lanka": "CMB",
    "dhaka": "DAC", "bangladesh": "DAC",
    "islamabad": "ISB", "lahore": "LHE", "karachi": "KHI",
    "chennai": "MAA", "madras": "MAA",
    "bangalore": "BLR", "bengaluru": "BLR",
    "hyderabad": "HYD",
    "kolkata": "CCU", "calcutta": "CCU",
    "goa": "GOI",

    # Southeast Asia
    "manila": "MNL", "philippines": "MNL",
    "hanoi": "HAN", "ho chi minh": "SGN", "saigon": "SGN",
    "phnom penh": "PNH", "cambodia": "PNH",
    "bali": "DPS",
    "phuket": "HKT",
    "taipei": "TPE", "taiwan": "TPE",

    # Middle East / Africa
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

    # Americas
    "havana": "HAV", "cuba": "HAV",
    "san jose": "SJC", "costa rica": "SJO",
    "panama city": "PTY", "panama": "PTY",
    "santiago": "SCL", "chile": "SCL",
    "medellin": "MDE",
    "quito": "UIO", "ecuador": "UIO",
    "montevideo": "MVD", "uruguay": "MVD",

    # Oceania
    "auckland": "AKL", "new zealand": "AKL",
    "wellington": "WLG",
    "brisbane": "BNE",
    "perth": "PER",
    "fiji": "NAN",
}


def _resolve_airport(city_or_code: str) -> str:
    """Resolve a city name or airport code to IATA code."""
    text = city_or_code.strip().lower()
    # City name / alias lookup first (handles "nyc" -> "JFK", "la" -> "LAX")
    if text in CITY_TO_IATA:
        return CITY_TO_IATA[text]
    # Already an IATA code (3 letters not in our alias table)
    if len(text) == 3 and text.isalpha():
        return text.upper()
    # Partial match
    for city, code in CITY_TO_IATA.items():
        if text in city or city in text:
            return code
    # Not found — if it looks like an IATA code (3 uppercase letters), return it
    # Otherwise return as-is and let Google Flights try to resolve the city name
    upper = city_or_code.strip().upper()
    if len(upper) == 3 and upper.isalpha():
        return upper
    # Return the original text — Google Flights can resolve city names
    return city_or_code.strip()


def _parse_date(date_str: str) -> str:
    """Parse a human date string into YYYY-MM-DD format.
    
    Handles: 'March 15', 'Mar 15 2026', '2026-03-15', '3/15/2026', '3/15', 'next Friday'
    """
    if not date_str:
        return ""
    
    text = date_str.strip()
    
    # Already in YYYY-MM-DD
    if re.match(r'^\d{4}-\d{2}-\d{2}$', text):
        return text
    
    # Try standard date formats
    now = datetime.now()
    formats = [
        "%B %d, %Y",    # March 15, 2026
        "%B %d %Y",     # March 15 2026
        "%B %d",         # March 15
        "%b %d, %Y",    # Mar 15, 2026
        "%b %d %Y",     # Mar 15 2026
        "%b %d",         # Mar 15
        "%m/%d/%Y",     # 3/15/2026
        "%m/%d",         # 3/15
        "%m-%d-%Y",     # 3-15-2026
        "%Y/%m/%d",     # 2026/3/15
    ]
    
    for fmt in formats:
        try:
            parsed = datetime.strptime(text, fmt)
            # If no year was in the format, assume current/next year
            if "%Y" not in fmt and "%y" not in fmt:
                parsed = parsed.replace(year=now.year)
                # If the date has already passed, use next year
                if parsed < now:
                    parsed = parsed.replace(year=now.year + 1)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue
    
    # Relative dates
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
        # Use tomorrow as a reasonable "this month" start date
        return (now + timedelta(days=1)).strftime("%Y-%m-%d")
    
    # Try to extract a month name and use first day of that month
    import calendar
    for month_num in range(1, 13):
        month_name = calendar.month_name[month_num].lower()
        month_abbr = calendar.month_abbr[month_num].lower()
        if month_name in lower or month_abbr in lower:
            year = now.year
            target = datetime(year, month_num, 15)  # mid-month
            if target < now:
                target = target.replace(year=year + 1)
            return target.strftime("%Y-%m-%d")
    
    # Couldn't parse — use tomorrow as a safe default instead of raw text
    print(f"    ⚠️ Could not parse date '{text}', defaulting to tomorrow")
    return (now + timedelta(days=1)).strftime("%Y-%m-%d")


# ═══════════════════════════════════════════════════════
#  Google Flights — URL Construction + Scraping
# ═══════════════════════════════════════════════════════

def _build_google_flights_url(
    origin: str,
    destination: str,
    depart_date: str,
    return_date: str = "",
    passengers: int = 1,
    trip_type: str = "round_trip",  # round_trip | one_way
    cabin: str = "economy",        # economy | premium_economy | business | first
    stops: str = "any",            # any | nonstop | 1stop
    sort_by: str = "price",        # price | duration | departure
) -> str:
    """Construct a Google Flights search URL with all parameters encoded.
    
    Google Flights uses a natural language query parameter that works
    reliably without needing to reverse-engineer their internal URL format.
    """
    origin_code = _resolve_airport(origin)
    dest_code = _resolve_airport(destination)
    depart = _parse_date(depart_date)
    
    # Build natural language query that Google Flights understands
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
    encoded = urllib.parse.quote_plus(query)
    return f"https://www.google.com/travel/flights?q={encoded}"


def _extract_flight_data(page_text: str) -> list:
    """Parse Google Flights results text into structured flight data.
    
    Google Flights layout (each result spans ~10-15 lines):
      11:45 PM          <- depart time
       – 
      5:59 AM+1         <- arrive time  
      JetBlue           <- airline
      4 hr 14 min       <- duration
      SLC–JFK           <- route
      Nonstop           <- stops
      326 kg CO2e       <- emissions
      ...
      $697              <- price
      round trip
    
    Strategy: find price lines, then scan UP to find the flight block.
    """
    flights = []
    lines = page_text.split("\n")
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Look for price patterns like "$542 round trip" or "$354"
        price_match = re.search(r'\$[\d,]+', line)
        if price_match:
            price = price_match.group()
            
            # Use wider context — flight details are usually 10-15 lines BEFORE the price
            context_start = max(0, i - 15)
            context_end = min(len(lines), i + 3)
            context = "\n".join(lines[context_start:context_end])
            
            # Extract times (e.g., "7:16 AM" ... "10:00 AM")
            time_matches = re.findall(r'\d{1,2}:\d{2}\s*(?:AM|PM)', context)
            
            # Extract airports
            airport_matches = re.findall(r'\b([A-Z]{3})\b', context)
            airport_codes = [a for a in airport_matches if a not in (
                'THE', 'AND', 'FOR', 'NOT', 'ALL', 'NEW', 'USD', 'AVG',
                'TOP', 'SEE', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN',
            )]
            
            # Extract duration (e.g., "4 hr 14 min", "10 hr 50 min")
            duration_match = re.search(r'(\d+\s*hr?\s*(?:\d+\s*min)?)', context)
            duration = duration_match.group(1).strip() if duration_match else ""
            
            # Extract airline — search the context lines above the price
            airline = ""
            common_airlines = [
                "Delta", "United", "American", "Southwest", "JetBlue", "Spirit",
                "Frontier", "Alaska", "Hawaiian", "Sun Country", "Breeze",
                "Air Canada", "WestJet", "British Airways", "Lufthansa",
                "Emirates", "Qatar Airways", "Singapore Airlines", "Turkish Airlines",
                "Air France", "KLM", "Iberia", "Ryanair", "EasyJet",
                "Allegiant", "Avianca", "Copa", "Volaris", "VivaAerobus",
            ]
            # Check each line above price for airline names (more precise)
            for li in range(max(0, i - 12), i):
                line_text = lines[li].strip()
                for al in common_airlines:
                    if al.lower() == line_text.lower() or al.lower() in line_text.lower():
                        airline = al
                        break
                if airline:
                    break
            
            # Extract stops
            stops_text = "Nonstop"
            stop_match = re.search(r'(\d+)\s*stop', context, re.IGNORECASE)
            if stop_match:
                n = stop_match.group(1)
                stops_text = f"{n} stop{'s' if int(n) > 1 else ''}"
            elif "nonstop" in context.lower():
                stops_text = "Nonstop"
            
            # Build flight entry
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
            
            # Avoid duplicates (same price + airline + time)
            key = f"{price}_{airline}_{flight.get('depart_time', '')}"
            if not any(f"{f['price']}_{f['airline']}_{f.get('depart_time', '')}" == key for f in flights):
                flights.append(flight)
        
        i += 1
    
    # Sort by price (numeric)
    def price_num(f):
        try:
            return int(f["price"].replace("$", "").replace(",", ""))
        except (ValueError, KeyError):
            return 99999
    
    flights.sort(key=price_num)
    return flights


def _format_flights(flights: list, query_desc: str) -> str:
    """Format flights into a clean, readable report."""
    if not flights:
        return f"❌ No flights found for: {query_desc}\n\nTry different dates or a nearby airport."
    
    lines = [f"✈️ **Flight Search Results** — {query_desc}\n"]
    lines.append(f"Found {len(flights)} options (sorted by price):\n")
    lines.append(f"{'#':<3} {'Price':<10} {'Airline':<15} {'Depart':<10} {'Arrive':<10} {'Duration':<12} {'Stops'}")
    lines.append("─" * 80)
    
    for i, f in enumerate(flights[:15], 1):  # Show top 15
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
    
    # Summary
    cheapest = flights[0]
    lines.append(f"\n💰 **Cheapest**: {cheapest.get('price', '?')} — {cheapest.get('airline', '?')} ({cheapest.get('stops', '?')}, {cheapest.get('duration', '?')})")
    
    # Find cheapest nonstop
    nonstops = [f for f in flights if "nonstop" in f.get("stops", "").lower()]
    if nonstops:
        best_ns = nonstops[0]
        lines.append(f"✈️ **Cheapest Nonstop**: {best_ns.get('price', '?')} — {best_ns.get('airline', '?')} ({best_ns.get('duration', '?')})")
    
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════
#  Main Flight Search Function
# ═══════════════════════════════════════════════════════

def search_flights(
    origin: str,
    destination: str,
    depart_date: str,
    return_date: str = "",
    passengers: int = 1,
    trip_type: str = "round_trip",
    cabin: str = "economy",
    stops: str = "any",
    sort_by: str = "price",
    max_price: int = 0,
) -> dict:
    """Search for flights using Google Flights (URL-parameter approach).
    
    This constructs the full search URL with all filters encoded,
    navigates to it, and reads the results. No UI interaction needed.
    
    Args:
        origin: City name or IATA code (e.g., "Tampa", "TPA")
        destination: City name or IATA code (e.g., "New York", "JFK")
        depart_date: Departure date (e.g., "March 15", "2026-03-15")
        return_date: Return date (empty for one-way)
        passengers: Number of passengers (default 1)
        trip_type: "round_trip" or "one_way"
        cabin: "economy", "premium_economy", "business", "first"
        stops: "any", "nonstop", "1stop"
        sort_by: "price", "duration", "departure"
        max_price: Maximum price filter (0 = no limit)
    
    Returns:
        {"success": True/False, "content": str, "flights": list}
    """
    try:
        # Resolve inputs
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
        
        # Build the URL with all filters encoded
        url = _build_google_flights_url(
            origin=origin,
            destination=destination,
            depart_date=depart_date,
            return_date=return_date,
            passengers=passengers,
            trip_type=trip_type,
            cabin=cabin,
            stops=stops,
            sort_by=sort_by,
        )
        
        # Navigate to Google Flights using our OWN CDP connection
        # (isolated from TARS's browser agent to avoid lock contention)
        # Use a deadline instead of signal.alarm (works from any thread)
        deadline = time.time() + 45
        cdp = None
        try:
            cdp = CDP()
            cdp.ensure_connected()
            
            # Navigate
            cdp.send("Page.navigate", {"url": url})
            
            # Google Flights needs time to load results (AJAX-heavy)
            time.sleep(6)
            if time.time() > deadline:
                raise _FlightSearchTimeout("Flight search timed out")
            
            # Wait for results to appear — check for price indicators
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
            
            # Also try to get structured flight elements
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
            
            # Combine both text sources for better extraction
            combined_text = page_text + "\n" + (extended_text or "")
        except _FlightSearchTimeout:
            if cdp:
                try: cdp.close()
                except: pass
            return {
                "success": False,
                "content": "❌ Flight search timed out — browser took too long. Try again.",
                "flights": [],
            }
        finally:
            if cdp:
                try: cdp.close()
                except: pass
        
        # Parse the results
        flights = _extract_flight_data(combined_text)
        
        # Apply max_price filter if set
        if max_price > 0:
            flights = [f for f in flights if _price_num(f.get("price", "$99999")) <= max_price]
        
        # Format the report
        report = _format_flights(flights, query_desc)
        
        return {
            "success": True,
            "content": report,
            "flights": flights,
            "url": url,
            "source": "Google Flights",
        }
    
    except Exception as e:
        return {
            "success": False,
            "content": f"❌ Flight search failed: {str(e)}",
            "flights": [],
            "error": str(e),
        }


def _price_num(price_str: str) -> int:
    """Extract numeric price from string like '$542' or '$1,234'."""
    try:
        return int(re.sub(r'[^\d]', '', price_str))
    except (ValueError, TypeError):
        return 99999


# ═══════════════════════════════════════════════════════
#  Flight Report — Search + Excel + Email in One Shot
# ═══════════════════════════════════════════════════════

def search_flights_report(
    origin: str,
    destination: str,
    depart_date: str,
    return_date: str = "",
    passengers: int = 1,
    trip_type: str = "round_trip",
    cabin: str = "economy",
    stops: str = "any",
    sort_by: str = "price",
    max_price: int = 0,
    email_to: str = "",
) -> dict:
    """Search flights → generate Excel report → optionally email it.

    One tool call does the entire pipeline:
      1. search_flights (Google Flights)
      2. generate_excel (professional .xlsx with formatted table)
      3. mac_mail send (if email_to is provided)

    Returns:
        {"success": bool, "content": str, "flights": list,
         "excel_path": str, "emailed": bool}
    """
    from hands.report_gen import generate_excel
    from hands import mac_control as mac

    # ── Step 1: Search ──
    result = search_flights(
        origin=origin,
        destination=destination,
        depart_date=depart_date,
        return_date=return_date,
        passengers=passengers,
        trip_type=trip_type,
        cabin=cabin,
        stops=stops,
        sort_by=sort_by,
        max_price=max_price,
    )

    flights = result.get("flights", [])
    if not result.get("success") or not flights:
        return result  # Pass through the error

    origin_code = _resolve_airport(origin)
    dest_code = _resolve_airport(destination)
    depart = _parse_date(depart_date)

    # ── Step 2: Build Excel ──
    headers = ["#", "Price", "Airline", "Departure", "Arrival", "Duration", "Stops", "Route"]
    rows = []
    for i, f in enumerate(flights, 1):
        route = ""
        if f.get("from") and f.get("to"):
            route = f"{f['from']}→{f['to']}"
        rows.append([
            i,
            f.get("price", "—"),
            f.get("airline", "—"),
            f.get("depart_time", "—"),
            f.get("arrive_time", "—"),
            f.get("duration", "—"),
            f.get("stops", "—"),
            route or f"{origin_code}→{dest_code}",
        ])

    cheapest = flights[0]
    nonstops = [f for f in flights if "nonstop" in f.get("stops", "").lower()]
    summary = {
        "Total Options": str(len(flights)),
        "Cheapest": f"{cheapest.get('price', '?')} — {cheapest.get('airline', '?')} ({cheapest.get('stops', '?')})",
    }
    if nonstops:
        best_ns = nonstops[0]
        summary["Cheapest Nonstop"] = f"{best_ns.get('price', '?')} — {best_ns.get('airline', '?')} ({best_ns.get('duration', '?')})"
    summary["Search Date"] = datetime.now().strftime("%B %d, %Y")
    summary["Source"] = "Google Flights"

    title = f"Flights {origin_code} → {dest_code} — {depart}"
    excel_result = generate_excel(
        title=title,
        headers=headers,
        rows=rows,
        summary=summary,
        sheet_name="Flights",
    )

    if not excel_result.get("success"):
        return {
            "success": True,  # search worked, excel failed
            "content": result["content"] + f"\n\n⚠️ Excel failed: {excel_result.get('content')}",
            "flights": flights,
            "excel_path": "",
            "emailed": False,
        }

    excel_path = excel_result["path"]

    # ── Step 3: Email (if requested) ──
    emailed = False
    email_msg = ""
    if email_to:
        try:
            mail_result = mac.mail_send(
                to_address=email_to,
                subject=f"✈️ Flight Report: {origin_code} → {dest_code} ({depart})",
                body=(
                    f"Hi Abdullah,\n\n"
                    f"Here's your flight search report for {origin_code} → {dest_code} on {depart}.\n\n"
                    f"Found {len(flights)} options.\n"
                    f"Cheapest: {cheapest.get('price', '?')} — {cheapest.get('airline', '?')} ({cheapest.get('stops', '?')})\n"
                    + (f"Cheapest Nonstop: {best_ns.get('price', '?')} — {best_ns.get('airline', '?')}\n" if nonstops else "")
                    + f"\nFull details in the attached Excel.\n\n— TARS"
                ),
                attachment_path=excel_path,
            )
            if mail_result.get("success"):
                emailed = True
                email_msg = f"\n📧 Report emailed to {email_to}"
            else:
                email_msg = f"\n⚠️ Email failed: {mail_result.get('content', 'unknown error')}"
        except Exception as e:
            email_msg = f"\n⚠️ Email failed: {e}"

    content = result["content"] + f"\n\n📊 Excel saved: {excel_path}{email_msg}"

    # ── Step 4: Notify user via iMessage ──
    try:
        from voice.imessage_send import IMessageSender
        sender = IMessageSender()
        nonstop_line = ""
        if nonstops:
            best_ns = nonstops[0]
            nonstop_line = f"\n✈️ Best nonstop: {best_ns.get('price', '?')} — {best_ns.get('airline', '?')} ({best_ns.get('duration', '?')})"
        imsg = (
            f"✅ Flight report ready!\n\n"
            f"🛫 {origin_code} → {dest_code}\n"
            f"📅 {depart}" + (f" → {_parse_date(return_date)}" if return_date else "") + "\n"
            f"📊 Found {len(flights)} options\n"
            f"💰 Cheapest: {cheapest.get('price', '?')} — {cheapest.get('airline', '?')} ({cheapest.get('stops', '?')})"
            f"{nonstop_line}"
        )
        if emailed:
            imsg += f"\n\n📧 Report emailed to {email_to}"
        else:
            imsg += f"\n\n📊 Excel saved to ~/Documents/TARS_Reports/"
        sender.send(imsg)
    except Exception:
        pass  # Don't fail the pipeline over notification

    return {
        "success": True,
        "content": content,
        "flights": flights,
        "excel_path": excel_path,
        "emailed": emailed,
        "url": result.get("url", ""),
    }


# ═══════════════════════════════════════════════════════
#  Cheapest Date Finder — scan a date range
# ═══════════════════════════════════════════════════════

def find_cheapest_dates(
    origin: str,
    destination: str,
    start_date: str,
    end_date: str = "",
    trip_type: str = "one_way",
    cabin: str = "economy",
    stops: str = "any",
    email_to: str = "",
) -> dict:
    """Find the cheapest day to fly within a date range.

    Searches every few days across the range, finds the cheapest prices,
    and returns a date-vs-price comparison.  Generates an Excel report
    and optionally emails it.

    Args:
        origin/destination: City or IATA code
        start_date: Range start (e.g. "March 1")
        end_date:   Range end  (e.g. "March 31"). Defaults to +30 days.
        trip_type:  "one_way" or "round_trip"
        cabin/stops: filters
        email_to:   Email address to send the report (optional)

    Returns:
        {"success": bool, "content": str, "dates": list, "excel_path": str}
    """
    from hands.report_gen import generate_excel
    from hands import mac_control as mac

    origin_code = _resolve_airport(origin)
    dest_code = _resolve_airport(destination)

    start = datetime.strptime(_parse_date(start_date), "%Y-%m-%d")
    if end_date:
        end = datetime.strptime(_parse_date(end_date), "%Y-%m-%d")
    else:
        end = start + timedelta(days=30)

    # Clamp to future
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if start < today:
        start = today + timedelta(days=1)

    total_days = (end - start).days
    if total_days <= 0:
        return {"success": False, "content": "❌ end_date must be after start_date", "dates": []}

    # Decide sampling: every day if <=14 days, every 2-3 days otherwise
    if total_days <= 14:
        step = 1
    elif total_days <= 30:
        step = 2
    else:
        step = 3

    dates_to_search = []
    d = start
    while d <= end:
        dates_to_search.append(d)
        d += timedelta(days=step)
    # Always include end date
    if dates_to_search[-1] != end:
        dates_to_search.append(end)

    print(f"    ✈️ Scanning {len(dates_to_search)} dates: {origin_code}→{dest_code} ({start.strftime('%b %d')} – {end.strftime('%b %d')})")

    # ── Search each date ──
    date_results = []
    for dt in dates_to_search:
        date_str = dt.strftime("%Y-%m-%d")
        print(f"      📅 {date_str}...", end=" ", flush=True)
        try:
            r = search_flights(
                origin=origin,
                destination=destination,
                depart_date=date_str,
                trip_type=trip_type,
                cabin=cabin,
                stops=stops,
            )
            flights = r.get("flights", [])
            if flights:
                best = flights[0]
                price = _price_num(best.get("price", "$99999"))
                date_results.append({
                    "date": date_str,
                    "day": dt.strftime("%a"),
                    "price": best.get("price", "—"),
                    "price_num": price,
                    "airline": best.get("airline", "—"),
                    "stops": best.get("stops", "—"),
                    "duration": best.get("duration", "—"),
                    "depart_time": best.get("depart_time", "—"),
                    "options": len(flights),
                })
                print(f"{best.get('price', '?')} ({best.get('airline', '?')})")
            else:
                date_results.append({
                    "date": date_str,
                    "day": dt.strftime("%a"),
                    "price": "N/A",
                    "price_num": 99999,
                    "airline": "—",
                    "stops": "—",
                    "duration": "—",
                    "depart_time": "—",
                    "options": 0,
                })
                print("no results")
        except Exception as e:
            print(f"error: {e}")
            date_results.append({
                "date": date_str,
                "day": dt.strftime("%a"),
                "price": "Error",
                "price_num": 99999,
                "airline": "—",
                "stops": "—",
                "duration": "—",
                "depart_time": "—",
                "options": 0,
            })

    if not date_results:
        return {"success": False, "content": "❌ No results for any date in range", "dates": []}

    # Sort by price
    date_results.sort(key=lambda x: x["price_num"])

    # ── Build text report ──
    report_lines = [
        f"✈️ **Cheapest Dates: {origin_code} → {dest_code}**",
        f"📅 Range: {start.strftime('%b %d')} – {end.strftime('%b %d, %Y')}",
        f"Scanned {len(date_results)} dates\n",
        f"{'Date':<14} {'Day':<5} {'Price':<10} {'Airline':<15} {'Stops':<10} {'Duration'}",
        "─" * 70,
    ]
    for dr in date_results:
        report_lines.append(
            f"{dr['date']:<14} {dr['day']:<5} {dr['price']:<10} "
            f"{dr['airline']:<15} {dr['stops']:<10} {dr['duration']}"
        )

    cheapest = date_results[0]
    report_lines.append(f"\n🏆 **CHEAPEST**: {cheapest['date']} ({cheapest['day']}) — "
                        f"{cheapest['price']} on {cheapest['airline']} "
                        f"({cheapest['stops']}, {cheapest['duration']})")

    # Top 3
    if len(date_results) >= 3:
        report_lines.append("\n💡 Top 3 cheapest dates:")
        for i, dr in enumerate(date_results[:3], 1):
            report_lines.append(f"  {i}. {dr['date']} ({dr['day']}) — {dr['price']} ({dr['airline']})")

    report = "\n".join(report_lines)

    # ── Excel report ──
    headers = ["Date", "Day", "Price", "Airline", "Departure", "Duration", "Stops", "Options"]
    rows = []
    for dr in date_results:
        rows.append([
            dr["date"],
            dr["day"],
            dr["price"],
            dr["airline"],
            dr["depart_time"],
            dr["duration"],
            dr["stops"],
            dr["options"],
        ])

    title = f"Cheapest Dates {origin_code}→{dest_code} ({start.strftime('%b')} {start.year})"
    summary = {
        "Route": f"{origin_code} → {dest_code}",
        "Date Range": f"{start.strftime('%b %d')} – {end.strftime('%b %d, %Y')}",
        "Dates Scanned": str(len(date_results)),
        "Cheapest Date": f"{cheapest['date']} ({cheapest['day']})",
        "Cheapest Price": f"{cheapest['price']} — {cheapest['airline']}",
        "Source": "Google Flights",
    }

    excel_result = generate_excel(
        title=title,
        headers=headers,
        rows=rows,
        summary=summary,
        sheet_name="Cheapest Dates",
    )

    excel_path = excel_result.get("path", "")
    if excel_path:
        report += f"\n\n📊 Excel saved: {excel_path}"

    # ── Email (if requested) ──
    emailed = False
    if email_to and excel_path:
        try:
            mail_result = mac.mail_send(
                to_address=email_to,
                subject=f"✈️ Cheapest Dates: {origin_code}→{dest_code} ({start.strftime('%b %Y')})",
                body=(
                    f"Hi Abdullah,\n\n"
                    f"Scanned {len(date_results)} dates for {origin_code} → {dest_code}.\n\n"
                    f"🏆 Cheapest: {cheapest['date']} ({cheapest['day']}) — "
                    f"{cheapest['price']} on {cheapest['airline']}\n\n"
                    f"Full breakdown in the attached Excel.\n\n— TARS"
                ),
                attachment_path=excel_path,
            )
            if mail_result.get("success"):
                emailed = True
                report += f"\n📧 Report emailed to {email_to}"
            else:
                report += f"\n⚠️ Email failed: {mail_result.get('content', '')}"
        except Exception as e:
            report += f"\n⚠️ Email failed: {e}"

    # ── Notify user via iMessage ──
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
        if emailed:
            imsg += f"\n\n📧 Report emailed to {email_to}"
        else:
            imsg += f"\n\n📊 Excel saved to ~/Documents/TARS_Reports/"
        sender.send(imsg)
    except Exception:
        pass  # Don't fail the pipeline over notification

    return {
        "success": True,
        "content": report,
        "dates": date_results,
        "cheapest": cheapest,
        "excel_path": excel_path,
        "emailed": emailed,
    }

