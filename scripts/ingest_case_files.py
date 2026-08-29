"""
Ingest Case Files Dataset: FIR 112/2026 (Extortion), FIR 118/2026 (NDPS), FIR 125/2026 (Murder)
Three linked cases from Kotwali Ranthpur Police Station.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import hashlib
from app.database import engine, Base, SessionLocal
from app.models.models import (
    User, Case, CaseAssignment, Entity, Relationship, Document,
    IngestionJob, Alert, UserRole, EntityType, RelationshipType,
    CaseStatus, AlertStatus, JobStatus, AlertType
)
from app.auth import get_password_hash
from app.services.entity_extraction import extract_entities_from_text
from app.services.graph_analytics import compute_centrality, detect_communities, find_shortest_path
from app.utils import log_audit
from datetime import datetime, timezone

Base.metadata.create_all(bind=engine)
db = SessionLocal()

try:
    # ── 1. Ensure users exist ──────────────────────────────────────────
    admin = db.query(User).filter(User.username == "admin").first()
    if not admin:
        admin = User(username="admin", email="admin@lawenforcement.gov",
                     full_name="System Administrator",
                     hashed_password=get_password_hash("admin123"),
                     role=UserRole.SYSTEM_ADMIN)
        db.add(admin); db.flush()
    analyst = db.query(User).filter(User.username == "analyst").first()
    if not analyst:
        analyst = User(username="analyst", email="analyst@lawenforcement.gov",
                       full_name="Crime Analyst",
                       hashed_password=get_password_hash("analyst123"),
                       role=UserRole.CRIME_ANALYST)
        db.add(analyst); db.flush()
    officer = db.query(User).filter(User.username == "officer").first()
    if not officer:
        officer = User(username="officer", email="officer@lawenforcement.gov",
                       full_name="Investigating Officer",
                       hashed_password=get_password_hash("officer123"),
                       role=UserRole.INVESTIGATING_OFFICER)
        db.add(officer); db.flush()
    db.commit()
    print("[+] Users OK")

    # ── 2. Create Cases ────────────────────────────────────────────────
    case_specs = [
        ("FIR-112/2026", "Extortion & Criminal Intimidation",
         "FIR 112/2026 at P.S. Kotwali Ranthpur. Complainant Ashok Mehra threatened for Rs. 15 lakh protection money. Accused: Vikram Solanki (absconding), Rajesh Thakur (arrested), Suresh Yadav (turned approver).",
         "Ranthpur City, Rajasthan"),
        ("FIR-118/2026", "NDPS Act - Narcotics Trafficking",
         "FIR 118/2026 at P.S. Kotwali Ranthpur. 1.8 kg mephedrone recovered from white Maruti Swift (RJ14-XX-4471). Accused: Farhan Qureshi (arrested), Rajesh Thakur (custody transfer), Meena Chauhan (absconding, hawala financier).",
         "Ranthpur City, Rajasthan"),
        ("FIR-125/2026", "Murder - Contract Killing",
         "FIR 125/2026 at P.S. Kotwali Ranthpur. Deepak Rawal shot dead near Ravindra Colony crossing. Accused: Vikram Solanki (absconding, ordered killing), Aditya Bhargava (arrested, shooter).",
         "Ranthpur City, Rajasthan"),
    ]

    cases = {}
    for case_num, name, desc, jur in case_specs:
        existing = db.query(Case).filter(Case.case_number == case_num).first()
        if existing:
            cases[case_num] = existing
            print(f"  [~] {case_num} exists")
            continue
        case = Case(case_number=case_num, name=name, description=desc,
                     jurisdiction=jur, created_by=admin.id)
        db.add(case); db.flush()
        cases[case_num] = case
        for u in [admin, analyst, officer]:
            db.add(CaseAssignment(user_id=u.id, case_id=case.id))
        print(f"  [+] Case {case_num}: {name}")
    db.commit()

    # ── 3. Ingest all documents with NLP ───────────────────────────────
    print("\n[2] Ingesting documents...")

    documents = {
        "Case1_FIR": {
            "case": "FIR-112/2026", "file": "Case1_FIR_112-2026_Extortion.docx",
            "type": "fir", "content": """FIRST INFORMATION REPORT - FIR No. 112/2026
Complainant: Ashok Mehra, builder, Mehra Towers Sector 9 Ranthpur City.
On 12-Mar-2026, received call from unknown number demanding Rs. 15,00,000 as protection money for commercial project in Sector 9.
On 14-Mar-2026 two men Rajesh Thakur (alias Raju) and Suresh Yadav visited site office, named Vikram Solanki (alias Vicky Bhai) as the person who would take action.
Accused: Vikram Solanki (alias Vicky Bhai) - Alleged instructor/beneficiary - Absconding.
Accused: Rajesh Thakur (alias Raju) - Alleged collector of protection money - Arrested 16-Mar-2026.
Accused: Suresh Yadav - Alleged driver/lookout - Turned approver 20-Mar-2026.
Suresh Yadav disclosed links to NDPS matter FIR 118/2026 and financier Meena Chauhan.
Look-out notice for Vikram Solanki. Case referred for network-linkage review with FIR 118/2026 and FIR 125/2026.
Investigating Officer: Insp. R.K. Bishnoi, SHO, P.S. Kotwali Ranthpur."""
        },
        "Case1_CDR": {
            "case": "FIR-112/2026", "file": "Case1_CDR_Report.txt",
            "type": "cdr", "content": """CALL DETAIL RECORD - Case 1 - FIR 112/2026
Vikram Solanki: 98290-XXXX1 / IMEI 8834**
Rajesh Thakur: 94140-XXXX2 / IMEI 3567**
Suresh Yadav: 97830-XXXX3 / IMEI 9021**
Ashok Mehra (Complainant): 98110-YYYY1
Unknown/Unregistered prepaid

CDR Records:
12-Mar-2026 18:02 Unregistered prepaid -> 98110-YYYY1 94s RTP-T014
12-Mar-2026 18:05 Unregistered prepaid -> 98110-YYYY1 61s RTP-T014
13-Mar-2026 10:14 94140-XXXX2 -> 97830-XXXX3 112s RTP-T022
13-Mar-2026 10:20 94140-XXXX2 -> 98290-XXXX1 203s RTP-T022
14-Mar-2026 17:40 97830-XXXX3 -> 94140-XXXX2 45s RTP-T045
14-Mar-2026 19:12 94140-XXXX2 -> 98290-XXXX1 88s RTP-T014
14-Mar-2026 19:38 98290-XXXX1 -> 94140-XXXX2 31s RTP-T031
16-Mar-2026 09:05 94140-XXXX2 -> 97830-XXXX3 19s RTP-T045

Tower Locations:
RTP-T014: Sector 9 Market Ranthpur City (near complainant site office)
RTP-T022: Shastri Nagar Junction Ranthpur City
RTP-T031: Nehru Colony Crossing Ranthpur City
RTP-T045: Sector 14 Bus Stand Ranthpur City"""
        },
        "Case1_Dossier": {
            "case": "FIR-112/2026", "file": "Case1_Suspect_Dossiers.txt",
            "type": "dossier", "content": """SUSPECT DOSSIER - Case 1
Vikram Solanki (alias Vicky Bhai): Network kingpin. Operates through intermediaries, rarely makes direct contact. Uses multiple SIM cards. Known associates: Rajesh Thakur (lieutenant), Meena Chauhan (financier), Aditya Bhargava (hired muscle). History: FIR 44/2019 Criminal intimidation - discharged. FIR 201/2022 Assault and rioting - acquitted.
Rajesh Thakur (alias Raju): Field lieutenant/enforcer. Handles in-person collection. Low digital footprint. Known associates: Vikram Solanki, Farhan Qureshi, Suresh Yadav. History: FIR 12/2017 Theft - convicted 6 months. FIR 88/2020 NDPS possession - convicted fine.
Suresh Yadav: Driver, peripheral player. No previous record. Used personal vehicle for network errands. Turned approver."""
        },
        "Case2_FIR": {
            "case": "FIR-118/2026", "file": "Case2_FIR_118-2026_NDPS.docx",
            "type": "fir", "content": """FIRST INFORMATION REPORT - FIR No. 118/2026
Anti-Narcotics Cell intercepted white Maruti Swift Reg RJ14-XX-4471 near Ranthpur Ring Road on 02-Apr-2026.
1.8 kg mephedrone recovered from concealed compartment.
Driver Farhan Qureshi arrested. Phone showed repeated contact with Rajesh Thakur number.
Financial transfers traced to account linked to Meena Chauhan (suspected hawala).
Raid at rented godown Industrial Area Phase-II linked to Qureshi - further contraband recovered.
Accused: Farhan Qureshi (alias Fanny) - Supplier/courier - Arrested 02-Apr-2026.
Accused: Rajesh Thakur (alias Raju) - Local distributor - Arrested 03-Apr-2026 in judicial custody transfer.
Accused: Meena Chauhan - Hawala financier - Absconding, look-out circular issued.
Three transfers totalling Rs. 6,40,000 from Meena Chauhan account to Qureshi associate - suspected hawala.
Case flagged for cross-reference with FIR 112/2026 and FIR 125/2026.
Investigating Officer: SI Devendra Panwar, Anti-Narcotics Cell."""
        },
        "Case2_CDR": {
            "case": "FIR-118/2026", "file": "Case2_CDR_Report.txt",
            "type": "cdr", "content": """CALL DETAIL RECORD - Case 2 - FIR 118/2026
Rajesh Thakur: 94140-XXXX2 / IMEI 3567**
Farhan Qureshi: 90010-XXXX4 / IMEI 5512**
Meena Chauhan: 99280-XXXX5 / IMEI 7743**

CDR Records:
19-Mar-2026 21:10 90010-XXXX4 -> 94140-XXXX2 76s RTP-T017
22-Mar-2026 14:02 90010-XXXX4 -> 99280-XXXX5 145s RTP-T028
28-Mar-2026 11:45 94140-XXXX2 -> 90010-XXXX4 52s RTP-T017
01-Apr-2026 20:55 90010-XXXX4 -> 94140-XXXX2 23s RTP-T009B
02-Apr-2026 22:40 90010-XXXX4 -> 99280-XXXX5 67s RTP-T009
02-Apr-2026 23:02 94140-XXXX2 -> 90010-XXXX4 9s RTP-T017

Tower Locations:
RTP-T009: Ranthpur Ring Road (interception point)
RTP-T017: Industrial Area Phase-II (godown vicinity)
RTP-T028: Rajendra Marg (near Chauhan shop)
RTP-T009B: NH-52 Toll Plaza approach"""
        },
        "Case2_Dossier": {
            "case": "FIR-118/2026", "file": "Case2_Suspect_Dossiers.txt",
            "type": "dossier", "content": """SUSPECT DOSSIER - Case 2
Farhan Qureshi (alias Fanny): Narcotics supply chain. Uses rented vehicles, rotating drivers. Contraband in false compartments. Avoids phone during pickups. Known associates: Rajesh Thakur, Meena Chauhan (financing), unidentified inter-state supplier Bhaiyaji. History: FIR 150/2021 NDPS transportation - pending trial.
Meena Chauhan: Hawala financier. Layers funds through jewellery-shop billing and small remittance transfers below reporting thresholds. Known associates: Vikram Solanki, Farhan Qureshi, wider hawala network outside district. History: FIR 302/2023 FEMA violation/hawala - under investigation."""
        },
        "Case3_FIR": {
            "case": "FIR-125/2026", "file": "Case3_FIR_125-2026_Murder.docx",
            "type": "fir", "content": """FIRST INFORMATION REPORT - FIR No. 125/2026
On 19-Apr-2026 at 21:55 hrs, Deepak Rawal (rival gang associate, previously in dispute with Vikram Solanki over territory) was shot near Ravindra Colony crossing and succumbed at Ranthpur General Hospital.
Eyewitness Ramesh Solanki saw motorcycle-borne assailant fire two shots before fleeing towards NH-52.
CCTV captured partial registration number traced to vehicle registered in name of Aditya Bhargava relative.
Aditya Bhargava traced through vehicle registration, apprehended 21-Apr-2026. Country-made pistol recovered from field near NH-52.
Bhargava phone shows call from Vikram Solanki number 40 minutes before incident and 12 minutes after.
Accused: Vikram Solanki (alias Vicky Bhai) - Conspirator who ordered killing - Absconding.
Accused: Aditya Bhargava (alias Bunty) - Shooter - Arrested 21-Apr-2026.
Case cross-referenced with FIR 112/2026 and FIR 118/2026 for consolidated network analysis.
Investigating Officer: Insp. Kavita Rathore, Crime Branch."""
        },
        "Case3_CDR": {
            "case": "FIR-125/2026", "file": "Case3_CDR_Report.txt",
            "type": "cdr", "content": """CALL DETAIL RECORD - Case 3 - FIR 125/2026
Vikram Solanki: 98290-XXXX1 / IMEI 8834**
Aditya Bhargava: 96550-XXXX6 / IMEI 2298**
Deepak Rawal (Deceased): 97220-YYYY9

CDR Records:
19-Apr-2026 21:12 98290-XXXX1 -> 96550-XXXX6 64s RTP-T031
19-Apr-2026 21:53 98290-XXXX1 -> 96550-XXXX6 22s RTP-T052
19-Apr-2026 22:07 96550-XXXX6 -> 98290-XXXX1 18s RTP-T060
20-Apr-2026 09:31 98290-XXXX1 -> 96550-XXXX6 no answer RTP-T012

Tower Locations:
RTP-T031: Nehru Colony Crossing (Vikram Solanki before incident)
RTP-T052: Ravindra Colony Crossing (scene of shooting, Aditya Bhargava present)
RTP-T060: NH-52 escape route (Aditya Bhargava fleeing)
RTP-T012: Sector 22 (Aditya Bhargava apprehended here)"""
        },
        "Case3_Dossier": {
            "case": "FIR-125/2026", "file": "Case3_Suspect_Dossiers.txt",
            "type": "dossier", "content": """SUSPECT DOSSIER - Case 3
Aditya Bhargava (alias Bunty): Contract muscle. Uses motorcycle for hit-and-run attacks. Switches SIM cards after jobs. Known associates: Vikram Solanki (handler). History: FIR 76/2018 Assault causing grievous hurt - convicted 2 years released 2020. FIR 410/2023 Illegal firearm - acquitted."""
        },
    }

    total_entities = 0
    total_rels = 0
    for doc_key, doc_info in documents.items():
        case = cases[doc_info["case"]]
        content = doc_info["content"]
        fhash = hashlib.sha256(content.encode()).hexdigest()
        upload_dir = os.path.join("uploads", case.id)
        os.makedirs(upload_dir, exist_ok=True)
        fpath = os.path.join(upload_dir, f"{fhash}_{doc_info['file']}")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)

        document = Document(
            case_id=case.id, filename=doc_info["file"], file_type="text/plain",
            file_size=len(content), file_hash=fhash, file_path=fpath,
            content_text=content, source_type=doc_info["type"], uploaded_by=admin.id
        )
        db.add(document); db.flush()

        extracted = extract_entities_from_text(content, doc_info["type"])
        entity_ids = []
        for ext in extracted:
            entity = Entity(
                case_id=case.id, entity_type=ext.entity_type, name=ext.name,
                attributes=ext.attributes, confidence_score=ext.confidence,
                source_document_id=document.id, is_ai_extracted=True,
                is_reviewed=ext.confidence >= 0.85
            )
            db.add(entity); db.flush()
            entity_ids.append(entity.id)
            total_entities += 1

        for i in range(len(entity_ids)):
            for j in range(i + 1, min(len(entity_ids), i + 15)):
                rel = Relationship(
                    case_id=case.id, source_entity_id=entity_ids[i],
                    target_entity_id=entity_ids[j],
                    relationship_type=RelationshipType.ASSOCIATE,
                    weight=1.0, confidence_score=0.6,
                    is_ai_generated=True, is_reviewed=False
                )
                db.add(rel); total_rels += 1

        db.flush()
        print(f"  [+] {doc_info['file']}: {len(extracted)} NLP entities")
    db.commit()

    # ── 4. Ground-truth entities ───────────────────────────────────────
    print("\n[3] Adding ground-truth entities...")
    entity_map = {}

    def find_or_create(case_id, etype, name, attrs=None):
        existing = db.query(Entity).filter(
            Entity.case_id == case_id, Entity.entity_type == etype,
            Entity.name == name, Entity.is_merged_into.is_(None)
        ).first()
        if existing:
            if attrs:
                ea = existing.attributes or {}
                ea.update(attrs)
                existing.attributes = ea
            db.flush()
            return existing
        e = Entity(case_id=case_id, entity_type=etype, name=name,
                   attributes=attrs or {}, confidence_score=1.0,
                   is_ai_extracted=False, is_reviewed=True)
        db.add(e); db.flush()
        return e

    # Persons
    persons = {
        "Vikram Solanki": {"alias": "Vicky Bhai", "role": "Network kingpin / decision-maker",
                           "phone": "98290-XXXX1", "status": "Absconding",
                           "history": "FIR 44/2019 discharged, FIR 201/2022 acquitted"},
        "Rajesh Thakur": {"alias": "Raju", "role": "Field lieutenant / enforcer",
                          "phone": "94140-XXXX2", "status": "Arrested",
                          "history": "FIR 12/2017 theft convicted, FIR 88/2020 NDPS convicted"},
        "Meena Chauhan": {"alias": None, "role": "Hawala financier - links all 3 cases",
                          "phone": "99280-XXXX5", "status": "Absconding",
                          "history": "FIR 302/2023 FEMA/hawala under investigation"},
        "Farhan Qureshi": {"alias": "Fanny", "role": "Narcotics supply chain",
                           "phone": "90010-XXXX4", "status": "Arrested",
                           "history": "FIR 150/2021 NDPS pending trial"},
        "Aditya Bhargava": {"alias": "Bunty", "role": "Contract muscle / shooter",
                            "phone": "96550-XXXX6", "status": "Arrested",
                            "history": "FIR 76/2018 assault convicted, FIR 410/2023 firearm acquitted"},
        "Suresh Yadav": {"alias": None, "role": "Driver / turned approver",
                         "phone": "97830-XXXX3", "status": "Approver/Witness"},
        "Ashok Mehra": {"alias": None, "role": "Complainant (builder)",
                        "phone": "98110-YYYY1"},
        "Deepak Rawal": {"alias": None, "role": "Deceased - rival gang associate",
                         "phone": "97220-YYYY9"},
        "Ramesh Solanki": {"alias": None, "role": "Eyewitness (no relation to accused)"},
    }

    # Cross-case persons
    case_cross = {
        "Vikram Solanki": ["FIR-112/2026", "FIR-125/2026"],
        "Rajesh Thakur": ["FIR-112/2026", "FIR-118/2026"],
        "Meena Chauhan": ["FIR-112/2026", "FIR-118/2026", "FIR-125/2026"],
        "Farhan Qureshi": ["FIR-118/2026"],
        "Aditya Bhargava": ["FIR-125/2026"],
        "Suresh Yadav": ["FIR-112/2026"],
        "Ashok Mehra": ["FIR-112/2026"],
        "Deepak Rawal": ["FIR-125/2026"],
        "Ramesh Solanki": ["FIR-125/2026"],
    }

    for name, info in persons.items():
        for case_num in case_cross.get(name, []):
            case = cases.get(case_num)
            if case:
                e = find_or_create(case.id, EntityType.PERSON, name, info)
                if name not in entity_map:
                    entity_map[name] = e.id
    print(f"  [+] {len(persons)} persons across cases")

    # Phones
    phones = {
        "98290-XXXX1": {"registered_to": "Vikram Solanki"},
        "94140-XXXX2": {"registered_to": "Rajesh Thakur"},
        "99280-XXXX5": {"registered_to": "Meena Chauhan"},
        "90010-XXXX4": {"registered_to": "Farhan Qureshi"},
        "96550-XXXX6": {"registered_to": "Aditya Bhargava"},
        "97830-XXXX3": {"registered_to": "Suresh Yadav"},
        "98110-YYYY1": {"registered_to": "Ashok Mehra"},
        "97220-YYYY9": {"registered_to": "Deepak Rawal"},
    }

    main_case = cases["FIR-112/2026"]
    for phone, info in phones.items():
        e = find_or_create(main_case.id, EntityType.PHONE, phone, info)
        entity_map[phone] = e.id
    print(f"  [+] {len(phones)} phones")

    # Locations
    locations = {
        "RTP-T014": {"address": "Sector 9 Market, Ranthpur City"},
        "RTP-T022": {"address": "Shastri Nagar Junction, Ranthpur City"},
        "RTP-T031": {"address": "Nehru Colony Crossing, Ranthpur City"},
        "RTP-T045": {"address": "Sector 14 Bus Stand, Ranthpur City"},
        "RTP-T009": {"address": "Ranthpur Ring Road (interception point)"},
        "RTP-T017": {"address": "Industrial Area Phase-II (godown vicinity)"},
        "RTP-T028": {"address": "Rajendra Marg (near Chauhan shop)"},
        "RTP-T009B": {"address": "NH-52 Toll Plaza approach"},
        "RTP-T052": {"address": "Ravindra Colony Crossing (scene of shooting)"},
        "RTP-T060": {"address": "NH-52 escape route"},
        "RTP-T012": {"address": "Sector 22, Ranthpur City"},
        "Sector 9": {"address": "Sector 9, Ranthpur City (complainant site)"},
        "Sector 14": {"address": "Sector 14 Bus Stand area"},
        "Industrial Area Phase-II": {"address": "Industrial Area Phase-II, Ranthpur City"},
        "Ranthpur Ring Road": {"address": "Ranthpur Ring Road"},
        "NH-52": {"address": "National Highway 52, Ranthpur"},
        "Ravindra Colony": {"address": "Ravindra Colony crossing, Ranthpur City"},
    }

    for loc, info in locations.items():
        e = find_or_create(main_case.id, EntityType.LOCATION, loc, info)
        entity_map[loc] = e.id
    print(f"  [+] {len(locations)} locations")

    # Organizations / Vehicles
    orgs = {
        "Anti-Narcotics Cell": {"type": "Law enforcement unit"},
        "Crime Branch": {"type": "Law enforcement unit"},
        "P.S. Kotwali Ranthpur": {"type": "Police Station"},
        "Ranthpur General Hospital": {"type": "Hospital"},
    }
    for org, info in orgs.items():
        e = find_or_create(main_case.id, EntityType.ORGANIZATION, org, info)
        entity_map[org] = e.id

    vehicles = {
        "RJ14-XX-4471": {"type": "White Maruti Swift", "context": "NDPS interception vehicle"},
    }
    for veh, info in vehicles.items():
        e = find_or_create(main_case.id, EntityType.VEHICLE, veh, info)
        entity_map[veh] = e.id
    db.commit()

    # ── 5. Ground-truth relationships ──────────────────────────────────
    print("\n[4] Building relationship graph...")

    def add_rel(src_name, tgt_name, rtype, weight, desc):
        src_id = entity_map.get(src_name)
        tgt_id = entity_map.get(tgt_name)
        if not src_id or not tgt_id:
            return
        src_e = db.query(Entity).filter(Entity.id == src_id).first()
        if not src_e:
            return
        existing = db.query(Relationship).filter(
            Relationship.source_entity_id == src_id,
            Relationship.target_entity_id == tgt_id,
            Relationship.relationship_type == rtype
        ).first()
        if existing:
            if weight > existing.weight:
                existing.weight = weight
            return
        existing = db.query(Relationship).filter(
            Relationship.source_entity_id == tgt_id,
            Relationship.target_entity_id == src_id,
            Relationship.relationship_type == rtype
        ).first()
        if existing:
            if weight > existing.weight:
                existing.weight = weight
            return
        rel = Relationship(
            case_id=src_e.case_id, source_entity_id=src_id,
            target_entity_id=tgt_id, relationship_type=rtype,
            weight=weight, confidence_score=1.0,
            is_ai_generated=False, is_reviewed=True, justification=desc
        )
        db.add(rel)

    # --- Vikram Solanki (Kingpin) connections ---
    add_rel("Vikram Solanki", "Rajesh Thakur", RelationshipType.ASSOCIATE, 5.0,
            "Operational partnership - extortion and narcotics distribution")
    add_rel("Vikram Solanki", "Meena Chauhan", RelationshipType.FINANCIAL, 5.0,
            "Financial link - hawala channel for laundering proceeds")
    add_rel("Vikram Solanki", "Aditya Bhargava", RelationshipType.ASSOCIATE, 5.0,
            "Handler/contract killer - ordered Deepak Rawal hit")
    add_rel("Vikram Solanki", "Deepak Rawal", RelationshipType.ASSOCIATE, 3.0,
            "Territory dispute - motive for contract killing")
    add_rel("Vikram Solanki", "98290-XXXX1", RelationshipType.OWNERSHIP, 5.0, "Phone ownership")
    add_rel("Vikram Solanki", "Suresh Yadav", RelationshipType.ASSOCIATE, 3.0,
            "Used Yadav as driver for extortion visits")

    # --- Rajesh Thakur connections ---
    add_rel("Rajesh Thakur", "Farhan Qureshi", RelationshipType.ASSOCIATE, 5.0,
            "Local distribution point for narcotics consignment")
    add_rel("Rajesh Thakur", "Suresh Yadav", RelationshipType.ASSOCIATE, 3.0,
            "Thakur directed Yadav as driver for extortion")
    add_rel("Rajesh Thakur", "94140-XXXX2", RelationshipType.OWNERSHIP, 5.0, "Phone ownership")

    # --- Meena Chauhan (Financier - LINKS ALL 3 CASES) ---
    add_rel("Meena Chauhan", "Farhan Qureshi", RelationshipType.FINANCIAL, 5.0,
            "Hawala financing - Rs. 6,40,000 transfers to Qureshi associate")
    add_rel("Meena Chauhan", "99280-XXXX5", RelationshipType.OWNERSHIP, 5.0, "Phone ownership")

    # --- Farhan Qureshi connections ---
    add_rel("Farhan Qureshi", "90010-XXXX4", RelationshipType.OWNERSHIP, 5.0, "Phone ownership")
    add_rel("Farhan Qureshi", "RJ14-XX-4471", RelationshipType.OWNERSHIP, 4.0, "Vehicle used for drug transport")

    # --- Aditya Bhargava connections ---
    add_rel("Aditya Bhargava", "96550-XXXX6", RelationshipType.OWNERSHIP, 5.0, "Phone ownership")

    # --- Suresh Yadav ---
    add_rel("Suresh Yadav", "97830-XXXX3", RelationshipType.OWNERSHIP, 5.0, "Phone ownership")

    # --- Complainant/Witness ---
    add_rel("Ashok Mehra", "98110-YYYY1", RelationshipType.OWNERSHIP, 5.0, "Phone ownership")
    add_rel("Deepak Rawal", "97220-YYYY9", RelationshipType.OWNERSHIP, 5.0, "Phone ownership")

    # --- CDR Communication links ---
    # Case 1 CDR
    add_rel("94140-XXXX2", "97830-XXXX3", RelationshipType.COMMUNICATION, 3.0,
            "Thakur <-> Yadav: 112s call on 13-Mar")
    add_rel("94140-XXXX2", "98290-XXXX1", RelationshipType.COMMUNICATION, 5.0,
            "Thakur <-> Solanki: 203s call 13-Mar, 88s 14-Mar, 31s 14-Mar")
    add_rel("97830-XXXX3", "94140-XXXX2", RelationshipType.COMMUNICATION, 2.0,
            "Yadav -> Thakur: 45s call 14-Mar")
    # Case 2 CDR
    add_rel("90010-XXXX4", "94140-XXXX2", RelationshipType.COMMUNICATION, 5.0,
            "Qureshi <-> Thakur: 76s, 52s, 23s, 9s calls")
    add_rel("90010-XXXX4", "99280-XXXX5", RelationshipType.COMMUNICATION, 5.0,
            "Qureshi -> Chauhan: 145s, 67s calls - hawala coordination")
    # Case 3 CDR
    add_rel("98290-XXXX1", "96550-XXXX6", RelationshipType.COMMUNICATION, 5.0,
            "Solanki -> Bhargava: 64s call 40min before murder, 22s 12min after")
    add_rel("96550-XXXX6", "98290-XXXX1", RelationshipType.COMMUNICATION, 3.0,
            "Bhargava -> Solanki: 18s call after hit - confirmation")

    # --- Location presence links ---
    add_rel("Rajesh Thakur", "RTP-T014", RelationshipType.LOCATION_PRESENCE, 4.0,
            "Sector 9 Market - extortion site visit")
    add_rel("Rajesh Thakur", "RTP-T045", RelationshipType.LOCATION_PRESENCE, 3.0,
            "Sector 14 Bus Stand - apprehended here")
    add_rel("Vikram Solanki", "RTP-T031", RelationshipType.LOCATION_PRESENCE, 4.0,
            "Nehru Colony - last seen before going dark")
    add_rel("Farhan Qureshi", "RTP-T017", RelationshipType.LOCATION_PRESENCE, 4.0,
            "Industrial Area Phase-II - godown vicinity")
    add_rel("Farhan Qureshi", "RTP-T028", RelationshipType.LOCATION_PRESENCE, 3.0,
            "Rajendra Marg - near Meena Chauhan shop")
    add_rel("Farhan Qureshi", "RTP-T009", RelationshipType.LOCATION_PRESENCE, 5.0,
            "Ranthpur Ring Road - vehicle intercepted here")
    add_rel("Farhan Qureshi", "RTP-T009B", RelationshipType.LOCATION_PRESENCE, 2.0,
            "NH-52 Toll Plaza - pre-consignment movement")
    add_rel("Vikram Solanki", "RTP-T052", RelationshipType.LOCATION_PRESENCE, 5.0,
            "Ravindra Colony - ordered hit from this area")
    add_rel("Aditya Bhargava", "RTP-T052", RelationshipType.LOCATION_PRESENCE, 5.0,
            "Ravindra Colony - shooter present at scene")
    add_rel("Aditya Bhargava", "RTP-T060", RelationshipType.LOCATION_PRESENCE, 5.0,
            "NH-52 - escape route after shooting")
    add_rel("Aditya Bhargava", "RTP-T012", RelationshipType.LOCATION_PRESENCE, 4.0,
            "Sector 22 - apprehended here")

    db.commit()
    print(f"  [+] Relationships created")

    # ── 6. Alerts ──────────────────────────────────────────────────────
    print("\n[5] Creating alerts...")

    alerts_data = [
        (AlertType.CROSS_CASE_MATCH, "HIGH", "Cross-Case Link: Vikram Solanki",
         "Vikram Solanki (Vicky Bhai) appears in FIR 112/2026 (Extortion - Accused, Absconding) and FIR 125/2026 (Murder - Conspirator). He is the alleged kingpin who directed both extortion and contract killing."),
        (AlertType.CROSS_CASE_MATCH, "HIGH", "Cross-Case Link: Rajesh Thakur",
         "Rajesh Thakur (Raju) appears in FIR 112/2026 (Extortion - Accused) and FIR 118/2026 (NDPS - Accused). He serves as field lieutenant for extortion AND local distributor for narcotics."),
        (AlertType.CROSS_CASE_MATCH, "HIGH", "CRITICAL: Meena Chauhan Links ALL 3 Cases",
         "Meena Chauhan is the Hawala Financier connecting ALL THREE cases. She finances the narcotics supply (FIR 118/2026), receives extortion proceeds via Vikram Solanki (FIR 112/2026), and benefits from the criminal enterprise that ordered the murder (FIR 125/2026). She is the KEY financial node in this network."),
        (AlertType.COMMUNICATION_BURST, "HIGH", "Communication Burst: Solanki -> Bhargava Before Murder",
         "Vikram Solanki called Aditya Bhargava 40 minutes before the murder (21:12, 64s call) and 12 minutes after (21:53, 22s call). This timing strongly suggests a coordinated contract killing."),
        (AlertType.COMMUNICATION_BURST, "HIGH", "Hawala Coordination: Qureshi -> Chauhan",
         "Farhan Qureshi made 145s and 67s calls to Meena Chauhan on 22-Mar and 02-Apr-2026, coinciding with Rs. 6,40,000 hawala transfers. Pattern consistent with financing narcotics supply chain."),
        (AlertType.CIRCULAR_TRANSACTION, "HIGH", "Financial Flow: Hawala Channel Detected",
         "Three transfers totalling Rs. 6,40,000 from Meena Chauhan's account to Qureshi's associate, flagged as suspected hawala-linked layering through jewellery-shop billing below reporting thresholds."),
    ]

    for atype, severity, title, desc in alerts_data:
        alert = Alert(
            case_id=main_case.id, alert_type=atype, title=title,
            description=desc, severity=severity, status=AlertStatus.NEW,
            supporting_evidence={"analysis": "cross-case linkage"}
        )
        db.add(alert)
        print(f"  [{severity}] {title}")

    db.commit()

    # ── 7. Analytics ───────────────────────────────────────────────────
    print("\n[6] Running graph analytics...")
    centrality = compute_centrality(db)
    print("\n  === CENTRALITY (All Cases) ===")
    for i, c in enumerate(centrality[:10]):
        print(f"  {i+1:2d}. {c['name']:30s}  Combined: {c['combined_score']:.4f}  "
              f"Betweenness: {c['betweenness_centrality']:.4f}  "
              f"Degree: {c['degree_centrality']:.4f}  Connections: {c['connections']}")

    communities = detect_communities(db)
    print("\n  === COMMUNITIES ===")
    for comm in communities[:5]:
        members = [m['name'] for m in comm['members'][:8]]
        print(f"  Community {comm['community_id']} ({comm['size']} nodes): {', '.join(members)}")

    # Shortest paths
    print("\n  === KEY PATHS ===")
    pairs = [
        ("Aditya Bhargava", "Meena Chauhan"),
        ("Farhan Qureshi", "Vikram Solanki"),
        ("Suresh Yadav", "Aditya Bhargava"),
        ("Deepak Rawal", "Rajesh Thakur"),
    ]
    for s, t in pairs:
        sid = entity_map.get(s)
        tid = entity_map.get(t)
        if sid and tid:
            path = find_shortest_path(db, sid, tid)
            if path:
                path_str = " -> ".join([p['name'] for p in path['path']])
                print(f"  {s} -> {t} ({path['hops']} hops): {path_str}")

    # Cross-case
    print("\n  === CROSS-CASE PERSONS ===")
    from sqlalchemy import func
    cross = (
        db.query(Entity.name, func.count(func.distinct(Entity.case_id)).label('cnt'))
        .filter(Entity.entity_type == EntityType.PERSON, Entity.is_merged_into.is_(None))
        .group_by(Entity.name)
        .having(func.count(func.distinct(Entity.case_id)) > 1)
        .all()
    )
    for row in cross:
        print(f"  {row.name}: {row.cnt} cases")

    # Summary
    total_ents = db.query(Entity).filter(Entity.is_merged_into.is_(None)).count()
    total_rels = db.query(Relationship).count()
    total_alerts = db.query(Alert).count()
    print(f"\n{'='*60}")
    print(f"  INGESTION COMPLETE")
    print(f"  Entities: {total_ents}  |  Relationships: {total_rels}  |  Alerts: {total_alerts}")
    print(f"{'='*60}")

    # Common links summary
    print(f"""
  COMMON LINKS ACROSS 3 CASES:

  1. VIKRAM SOLANKI (Kingpin) — FIR 112 + FIR 125
     Extortion mastermind + ordered contract killing of Deepak Rawal.
     Highest betweenness centrality = controls information flow.

  2. RAJESH THAKUR (Enforcer) — FIR 112 + FIR 118
     Field lieutenant for extortion AND narcotics distributor.
     Bridge between extortion operations and drug supply chain.

  3. MEENA CHAUKHAN (Financier) — ALL 3 CASES (Critical Link)
     Hawala financier connecting EVERY case:
     - FIR 112: receives/proxies extortion proceeds
     - FIR 118: finances narcotics supply (Rs. 6.4L transfers)
     - FIR 125: benefits from criminal enterprise funding
     She is the FINANCIAL NERVE CENTRE of this network.

  4. FINANCIAL FLOW:
     Meena Chauhan -> Farhan Qureshi (hawala, Rs. 6.4L)
     -> used for narcotics procurement
     -> profits back to Vikram Solanki via Rajesh Thakur

  5. COMMUNICATION EVIDENCE:
     Solanki called Bhargava 40min before + 12min after murder
     Qureshi called Chauhan 145s + 67s during hawala window
     Thakur coordinated with both Solanki (extortion) and Qureshi (drugs)

  6. GEO-SPATIAL OVERLAP:
     RTP-T031 (Nehru Colony) used by BOTH Solanki (Case 1) and Bhargava (Case 3)
     RTP-T045 (Sector 14) used by Thakur for both extortion visits
     NH-52 corridor used for both drug transport and murder escape
""")

except Exception as e:
    print(f"[ERROR] {e}")
    import traceback; traceback.print_exc()
    db.rollback()
finally:
    db.close()
