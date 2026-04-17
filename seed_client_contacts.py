# ============================================================
# Seed 17 client contacts for WBOM
# Run once: python seed_client_contacts.py
# ============================================================
import os
import sys

# Add WBOM path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "fazle-system", "wbom"))

from database import get_conn, execute_query

CONTACTS = [
    # Escort buyers
    {"whatsapp_number": "01670535255", "display_name": "Escort Buyer 1", "relation_type": "Escort Buyer"},
    {"whatsapp_number": "01757622300", "display_name": "Escort Buyer 2", "relation_type": "Escort Buyer"},
    # Security guard buyers
    {"whatsapp_number": "01537443173", "display_name": "Security Buyer 1", "relation_type": "Security Guard Buyer"},
    {"whatsapp_number": "01829366960", "display_name": "Security Buyer 2", "relation_type": "Security Guard Buyer"},
    {"whatsapp_number": "01826532066", "display_name": "Security Buyer 3", "relation_type": "Security Guard Buyer"},
    {"whatsapp_number": "01995206164", "display_name": "Security Buyer 4", "relation_type": "Security Guard Buyer"},
    {"whatsapp_number": "01770981142", "display_name": "Security Buyer 5", "relation_type": "Security Guard Buyer"},
    {"whatsapp_number": "01671174137", "display_name": "Security Buyer 6", "relation_type": "Security Guard Buyer"},
    {"whatsapp_number": "01601509048", "display_name": "Security Buyer 7", "relation_type": "Security Guard Buyer"},
    {"whatsapp_number": "01580388149", "display_name": "Security Buyer 8", "relation_type": "Security Guard Buyer"},
    {"whatsapp_number": "01708314716", "display_name": "Security Buyer 9", "relation_type": "Security Guard Buyer"},
    {"whatsapp_number": "01974008172", "display_name": "Security Buyer 10", "relation_type": "Security Guard Buyer"},
    {"whatsapp_number": "01516115783", "display_name": "Security Buyer 11", "relation_type": "Security Guard Buyer"},
    {"whatsapp_number": "01735692001", "display_name": "Security Buyer 12", "relation_type": "Security Guard Buyer"},
    {"whatsapp_number": "01819312640", "display_name": "Security Buyer 13", "relation_type": "Security Guard Buyer"},
    {"whatsapp_number": "01760701010", "display_name": "Security Buyer 14", "relation_type": "Security Guard Buyer"},
    {"whatsapp_number": "01837747230", "display_name": "Security Buyer 15", "relation_type": "Security Guard Buyer"},
]


def seed():
    inserted = 0
    skipped = 0

    for c in CONTACTS:
        # Check if contact already exists
        existing = execute_query(
            "SELECT contact_id FROM wbom_contacts WHERE whatsapp_number = %s",
            (c["whatsapp_number"],),
        )
        if existing:
            print(f"  SKIP {c['whatsapp_number']} ({c['display_name']}) — already exists")
            skipped += 1
            continue

        # Ensure relation_type exists and get its ID
        rt_rows = execute_query(
            "SELECT type_id FROM wbom_relation_types WHERE type_name = %s",
            (c["relation_type"],),
        )
        if not rt_rows:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO wbom_relation_types (type_name) VALUES (%s) RETURNING type_id",
                        (c["relation_type"],),
                    )
                    rt_id = cur.fetchone()[0]
                conn.commit()
        else:
            rt_id = rt_rows[0]["type_id"]

        # Insert contact
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO wbom_contacts (whatsapp_number, display_name, relation_type_id) "
                    "VALUES (%s, %s, %s) RETURNING contact_id",
                    (c["whatsapp_number"], c["display_name"], rt_id),
                )
                cid = cur.fetchone()[0]
            conn.commit()
        print(f"  INSERT {c['whatsapp_number']} ({c['display_name']}) → contact_id={cid}")
        inserted += 1

    print(f"\nDone: {inserted} inserted, {skipped} skipped")


if __name__ == "__main__":
    seed()
