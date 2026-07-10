"""
Run this on your machine to find working Shopify stores.
Usage: python3 verify_stores_v2.py

Covers: sneakers, streetwear, fashion, beauty, electronics, lifestyle, watches, bags.
No food stores included.
"""
import urllib.request, json, ssl

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

# (name, base_url, category)
CANDIDATES = [
    # ── Sneakers / Streetwear ─────────────────────────────────────────────
    ("crepdogcrew",       "https://crepdogcrew.com",              "Sneakers/Streetwear"),
    ("sneakwear",         "https://sneakwear.in",                 "Sneakers/Streetwear"),
    ("hypeelixir",        "https://www.hypeelixir.com",           "Sneakers/Streetwear"),
    ("kicksmachine",      "https://www.kicksmachine.com",         "Sneakers/Streetwear"),
    ("yoursneakerstore",  "https://yoursneakerstore.in",          "Sneakers/Streetwear"),
    ("10hillsstudio",     "https://10hillsstudio.com",            "Sneakers/Streetwear"),
    ("superkicks",        "https://www.superkicks.in",            "Sneakers/Streetwear"),
    ("vegnonveg",         "https://vegnonveg.com",                "Sneakers/Streetwear"),
    ("findyourkicks",     "https://findyourkicks.in",             "Sneakers/Streetwear"),

    # ── Fashion / Apparel ─────────────────────────────────────────────────
    ("snitch",            "https://www.snitch.co.in",             "Fashion"),
    ("thesouledstore",    "https://www.thesouledstore.com",       "Fashion"),
    ("bewakoof",          "https://www.bewakoof.com",             "Fashion"),
    ("beyoung",           "https://www.beyoung.in",               "Fashion"),
    ("urbanic",           "https://in.urbanic.com",               "Fashion"),
    ("sassafras",         "https://www.sassafras.in",             "Fashion"),
    ("chumbak",           "https://www.chumbak.com",              "Lifestyle/Fashion"),
    ("neemans",           "https://www.neemans.com",              "Footwear"),
    ("flatheads",         "https://www.flatheads.in",             "Footwear"),
    ("toesox",            "https://toesox.in",                    "Footwear"),
    ("puma",              "https://in.puma.com",                  "Sneakers/Apparel"),

    # ── Beauty / Skincare ─────────────────────────────────────────────────
    ("pilgrim",           "https://www.pilgrimbeauty.com",        "Beauty"),
    ("foxtale",           "https://foxtale.in",                   "Beauty"),
    ("minimalist",        "https://beminimalist.co",              "Beauty/Skincare"),
    ("mcaffeine",         "https://www.mcaffeine.com",            "Beauty"),
    ("plum",              "https://plumgoodness.com",             "Beauty"),
    ("sugarpop",          "https://in.sugarcosmetics.com",        "Beauty"),
    ("wow",               "https://www.wowskinscience.com",       "Beauty"),
    ("mamaearth",         "https://mamaearth.in",                 "Beauty"),

    # ── Electronics / Audio / Wearables ──────────────────────────────────
    ("boat",              "https://www.boat-lifestyle.com",       "Electronics"),
    ("noise",             "https://www.gonoise.com",              "Electronics"),
    ("portronics",        "https://www.portronics.com",           "Electronics"),
    ("zebronics",         "https://zebronics.com",                "Electronics"),
    ("crossbeats",        "https://crossbeats.com",               "Electronics"),

    # ── Watches / Accessories ─────────────────────────────────────────────
    ("fastrack",          "https://www.fastrack.in",              "Watches"),
    ("titan",             "https://www.titan.co.in",              "Watches"),
    ("mvmt",              "https://in.mvmt.com",                  "Watches"),
    ("lowercase",         "https://lowercase.in",                 "Watches/Accessories"),

    # ── Home / Lifestyle ──────────────────────────────────────────────────
    ("pepperfry",         "https://www.pepperfry.com",            "Home"),
    ("wakefit",           "https://www.wakefit.co",               "Home"),
    ("thehouseofthings",  "https://thehouseofthings.com",         "Home Decor"),
    ("amalaearth",        "https://amalaearth.com",               "Lifestyle"),

    # ── Bags / Travel ─────────────────────────────────────────────────────
    ("nastygal",          "https://www.nasty-gal.in",             "Bags/Fashion"),
    ("dressberry",        "https://dressberry.in",                "Fashion/Bags"),
    ("eske",              "https://www.eske.in",                  "Bags/Leather"),
    ("baggit",            "https://baggit.com",                   "Bags"),
    ("harissons",         "https://www.harissons.com",            "Bags/Travel"),
]

ctx = ssl.create_default_context()

def check(name, base_url, category):
    url = f"{base_url}/products.json?limit=3"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=8, context=ctx) as r:
            data = json.loads(r.read())
        products = data.get("products", [])
        if not products:
            return None, "empty"
        p = products[0]
        v = p.get("variants", [{}])[0]
        return {
            "name": name,
            "base_url": base_url,
            "category": category,
            "sample_title": p["title"][:50],
            "vendor": p.get("vendor", ""),
            "product_type": p.get("product_type", ""),
            "option1_label": v.get("option1", "?"),
            "price": v.get("price", "?"),
            "tags": p.get("tags", []),
        }, "ok"
    except Exception as e:
        err = str(e)[:50]
        if "404" in err:   return None, "404 (not Shopify)"
        if "403" in err:   return None, "403 (Shopify, blocks API)"
        if "SSL" in err:   return None, "SSL error"
        if "Name or" in err: return None, "DNS fail (site down?)"
        return None, err

print(f"\n{'NAME':<22} {'CAT':<22} {'STATUS':<28} SAMPLE")
print("─" * 100)

working = []
blocked = []
dead = []

for name, base_url, category in CANDIDATES:
    info, status = check(name, base_url, category)
    if info:
        print(f"✓  {name:<20} {category:<22} {'OK':<28} {info['sample_title']}")
        print(f"   vendor={info['vendor']!r:<25} type={info['product_type']!r:<20} option1={info['option1_label']!r} price=₹{info['price']}")
        working.append(info)
    elif "403" in status:
        print(f"⚠  {name:<20} {category:<22} {status}")
        blocked.append((name, base_url, category))
    else:
        print(f"✗  {name:<20} {category:<22} {status}")
        dead.append(name)

print(f"\n{'─'*100}")
print(f"✓  {len(working)} working  |  ⚠ {len(blocked)} Shopify-but-blocked  |  ✗ {len(dead)} dead/non-Shopify")

if working:
    print(f"\nWorking stores (ready for JSON config):")
    for s in working:
        print(f"  {s['name']:<22} {s['category']}")

if blocked:
    print(f"\nBlocked stores (Shopify, need User-Agent fix or alternative endpoint):")
    for name, url, cat in blocked:
        print(f"  {name:<22} {url}")