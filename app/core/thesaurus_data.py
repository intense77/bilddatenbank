"""
Kirchlicher Thesaurus & Ikonographischer Standard für das Historische Bildarchiv.
Basiert auf:
- Iconclass (Standard für christliche Ikonographie, Bildarchiv Foto Marburg)
- GND (Gemeinsame Normdatei der Deutschen Nationalbibliothek)
- Getty AAT (Art & Architecture Thesaurus, dt. Begriffe für Vasa sacra und Paramente)
"""

from typing import Any, Dict, List, Optional


CHURCH_THESAURUS: List[Dict[str, Any]] = [
    # ================= 1. VASA SACRA & LITURGISCHE GERÄTE =================
    {
        "id": "vasa_monstranz",
        "canonical": "Monstranz",
        "category": "Vasa sacra",
        "synonyms": [
            "Ostensorium", "Allerheiligstes", "Strahlenmonstranz", "Turmmonstranz", 
            "Sakramentsschrein", "Sonnenmonstranz", "Aussetzung", "Hostienmonstranz"
        ],
        "iconclass": "11Q71441",
        "gnd": "4040126-1",
        "description": "Liturgisches Zeigegefäß zur feierlichen Aussetzung des Leibes Christi (Allerheiligstes).",
        "clip_prompts": [
            "golden monstrance ostensorium with host, sacred vessel catholic liturgy",
            "historical baroque monstrance on catholic altar"
        ]
    },
    {
        "id": "vasa_kelch",
        "canonical": "Kelch",
        "category": "Vasa sacra",
        "synonyms": [
            "Messkelch", "Abendmahlskelch", "Kelchvelum", "Calix", "Altarbecher"
        ],
        "iconclass": "11Q71442",
        "gnd": "4163565-1",
        "description": "Liturgisches Gefäß für den Messwein bei der Eucharistiefeier.",
        "clip_prompts": [
            "golden chalice mass communion cup, decorated catholic liturgy chalice",
            "priest elevating chalice at altar"
        ]
    },
    {
        "id": "vasa_ziborium",
        "canonical": "Ziborium",
        "category": "Vasa sacra",
        "synonyms": [
            "Speisekelch", "Hostienkelch", "Hostiendose", "Pyxis", "Ciborium"
        ],
        "iconclass": "11Q71443",
        "gnd": "4190822-4",
        "description": "Kelchförmiges Gefäß mit Deckel zur Aufbewahrung der konsekrierten Hostien im Tabernakel.",
        "clip_prompts": [
            "ciborium covered chalice for consecrated hosts, catholic church vessel"
        ]
    },
    {
        "id": "vasa_patene",
        "canonical": "Patene",
        "category": "Vasa sacra",
        "synonyms": ["Hostienteller", "Hostienschale", "Opferteller"],
        "iconclass": "11Q71444",
        "gnd": "4173516-7",
        "description": "Flacher runder Teller aus Edelmetall zur Aufnahme der Zelebrationshostie.",
        "clip_prompts": [
            "golden paten plate for communion host, altar vessel"
        ]
    },
    {
        "id": "vasa_weihrauchfass",
        "canonical": "Weihrauchfass",
        "category": "Vasa sacra",
        "synonyms": [
            "Thuribulum", "Rauchfass", "Weihrauch", "Weihrauchrauch", "Weihrauchschwingen"
        ],
        "iconclass": "11Q71446",
        "gnd": "4277708-3",
        "description": "Gefäß an Ketten zum Verbrennen von Weihharz (Weihrauch) bei festlichen Gottesdiensten.",
        "clip_prompts": [
            "thurible censer incense burner swinging chains, church liturgy incense smoke",
            "altar server holding thurible"
        ]
    },
    {
        "id": "vasa_weihrauchschiffchen",
        "canonical": "Weihrauchschiffchen",
        "category": "Vasa sacra",
        "synonyms": ["Schiffchen", "Naviculum", "Navicula", "Weihrauchlöffel"],
        "iconclass": "11Q71446(+1)",
        "gnd": "4392576-9",
        "description": "Schiffförmiges Behältnis für die Weihrauchkörner samt Löffelchen.",
        "clip_prompts": [
            "incense boat navicula sacred metal vessel, catholic liturgy"
        ]
    },
    {
        "id": "vasa_vortragekreuz",
        "canonical": "Vortragekreuz",
        "category": "Vasa sacra",
        "synonyms": [
            "Prozessionskreuz", "Vortragskreuz", "Prozessionsstange", "Crux processionalis"
        ],
        "iconclass": "11D1231",
        "gnd": "4188718-9",
        "description": "Kruzifix an langer Tragestange, das vor Prozessionen und beim Einzug getragen wird.",
        "clip_prompts": [
            "processional crucifix cross held by altar boy, church procession"
        ]
    },
    {
        "id": "vasa_aspergill",
        "canonical": "Aspergill",
        "category": "Vasa sacra",
        "synonyms": [
            "Weihwassersprengel", "Sprengel", "Weihwasserkessel", "Aspersorium", "Weihwasserwedel"
        ],
        "iconclass": "11Q71447",
        "gnd": "4335508-3",
        "description": "Liturgisches Gerät zum Besprengen mit Weihwasser bei Segnungen.",
        "clip_prompts": [
            "aspergillum holy water sprinkler and pail, catholic blessing ritual"
        ]
    },
    {
        "id": "vasa_messkaennchen",
        "canonical": "Messkännchen",
        "category": "Vasa sacra",
        "synonyms": ["Messkannen", "Kännchen", "Ampullen", "Altarampullen", "Wein und Wasser"],
        "iconclass": "11Q71445",
        "gnd": "4722883-9",
        "description": "Zwei Kännchen (aus Glas oder Metall) auf einem Tablett für Wein und Wasser.",
        "clip_prompts": [
            "cruets for communion water and wine on tray, altar vessel"
        ]
    },
    {
        "id": "vasa_reliquiar",
        "canonical": "Reliquiar",
        "category": "Vasa sacra",
        "synonyms": [
            "Reliquienschrein", "Reliquienbüste", "Reliquienkreuz", "Partikelmonstranz", 
            "Heiligenreliquie", "Reliquienkapsel", "Lipsanothek"
        ],
        "iconclass": "11Q7145",
        "gnd": "4177751-2",
        "description": "Kostbares Gefäß oder Schrein zur Aufbewahrung von Reliquien von Heiligen.",
        "clip_prompts": [
            "sacred reliquary reliquarium gold silver gothic shrine, saint relic vessel",
            "historical saint reliquary bust on altar"
        ]
    },

    # ================= 2. PARAMENTE & LITURGISCHE GEWÄNDER =================
    {
        "id": "par_kasel",
        "canonical": "Kasel",
        "category": "Paramente",
        "synonyms": [
            "Messgewand", "Planeta", "Casula", "Priestergewand", "Messgewänder", 
            "Glockenkasel", "Bassgeigenkasel", "Ornat", "Parament"
        ],
        "iconclass": "11Q71421",
        "gnd": "4163353-8",
        "description": "Hauptgewand des zelebrierenden Priesters bei der heiligen Messe.",
        "clip_prompts": [
            "chasuble liturgical vestment priest wearing casula at mass, embroidered baroque chasuble",
            "priest in golden embroidered chasuble celebrating mass"
        ]
    },
    {
        "id": "par_dalmatik",
        "canonical": "Dalmatik",
        "category": "Paramente",
        "synonyms": [
            "Diakonengewand", "Dalmatica", "Chorrock des Diakons", "Diakonenornat"
        ],
        "iconclass": "11Q71422",
        "gnd": "4229037-3",
        "description": "Liturgisches Obergewand des Diakons mit weiten Ärmeln.",
        "clip_prompts": [
            "dalmatic vestment deacon wearing embroidered dalmatica, catholic liturgy"
        ]
    },
    {
        "id": "par_albe",
        "canonical": "Albe",
        "category": "Paramente",
        "synonyms": [
            "Chorhemd", "Chorrock", "Priesterhemd", "Weißes Untergewand", "Alba"
        ],
        "iconclass": "11Q71423",
        "gnd": "4229036-1",
        "description": "Knöchellanges weißes Leinengewand, Grundgewand aller liturgischen Dienste.",
        "clip_prompts": [
            "white liturgical alb robe priest wearing white robe, church vestment"
        ]
    },
    {
        "id": "par_stola",
        "canonical": "Stola",
        "category": "Paramente",
        "synonyms": [
            "Priesterstola", "Diakonenstola", "Amtsbinde", "Schulterstreifen"
        ],
        "iconclass": "11Q71424",
        "gnd": "4183569-4",
        "description": "Schmaler langer Stoffstreifen um den Nacken, Amtsabzeichen des Priesters/Diakons.",
        "clip_prompts": [
            "priest stole liturgical stole neck vestment, embroidered cross stole"
        ]
    },
    {
        "id": "par_chormantel",
        "canonical": "Chormantel",
        "category": "Paramente",
        "synonyms": [
            "Pluviale", "Vespermantel", "Rauchmantel", "Segensmantel", "Capa"
        ],
        "iconclass": "11Q71425",
        "gnd": "4277709-5",
        "description": "Weiter Mantel bis zu den Füßen mit Spange auf der Brust, getragen bei Prozessionen und Vespern.",
        "clip_prompts": [
            "pluviale cope liturgical mantle priest wearing ornate cope, procession cloak"
        ]
    },
    {
        "id": "par_mitra",
        "canonical": "Mitra",
        "category": "Paramente",
        "synonyms": [
            "Bischofsmütze", "Inful", "Bischofshaube", "Mitren", "Zweispitz"
        ],
        "iconclass": "11P31111",
        "gnd": "4352833-8",
        "description": "Spitz zulaufende zeremonielle Kopfbedeckung von Bischöfen und Äbten mit zwei hängenden Bändern.",
        "clip_prompts": [
            "bishop wearing miter mitre tall ceremonial headdress, catholic bishop vestments"
        ]
    },
    {
        "id": "par_bischofsstab",
        "canonical": "Bischofsstab",
        "category": "Paramente",
        "synonyms": [
            "Krummstab", "Hirtenstab", "Abtsstab", "Baculus pastoralis", "Pastorale"
        ],
        "iconclass": "11P31112",
        "gnd": "4145700-1",
        "description": "Stab mit schneckenförmiger Krümme, Zeichen des Hirtenamts von Bischof und Abt.",
        "clip_prompts": [
            "crosier pastoral staff bishop holding golden shepherd crook, pontifical staff"
        ]
    },
    {
        "id": "par_birett",
        "canonical": "Birett",
        "category": "Paramente",
        "synonyms": ["Priesterhut", "Klerikermütze", "Vierkantbirett", "Biretta", "Pfarrermütze"],
        "iconclass": "11P312(+1)",
        "gnd": "4145660-4",
        "description": "Viereckige liturgische Kopfbedeckung katholischer Geistlicher mit drei oder vier Rippen.",
        "clip_prompts": [
            "black biretta priest hat three peaks pompom, traditional catholic priest hat"
        ]
    },
    {
        "id": "par_pallium",
        "canonical": "Pallium",
        "category": "Paramente",
        "synonyms": ["Erzbischofsstola", "Wollstola des Metropoliten", "Kreuzpallium"],
        "iconclass": "11P31113",
        "gnd": "4173151-4",
        "description": "Weißes Wollband mit sechs schwarzen Kreuzen, getragen von Metropoliten und Erzbischöfen.",
        "clip_prompts": [
            "archbishop wearing pallium woolen band with black crosses"
        ]
    },
    {
        "id": "par_schultervelum",
        "canonical": "Schultervelum",
        "category": "Paramente",
        "synonyms": ["Velum", "Humerale", "Sakramentsvelum", "Segensvelum"],
        "iconclass": "11Q71426",
        "gnd": "4437293-6",
        "description": "Breites Tuch, mit dem der Priester bei Segnungen mit der Monstranz die Hände verhüllt.",
        "clip_prompts": [
            "humeral veil shawl priest carrying monstrance, benediction ceremony"
        ]
    },
    {
        "id": "par_talar",
        "canonical": "Talar",
        "category": "Paramente",
        "synonyms": ["Soutane", "Habit", "Priesterkleid", "Kassette", "Knopfrock"],
        "iconclass": "11P3121",
        "gnd": "4184374-5",
        "description": "Knöchellanges schwarzes Gewand der katholischen Geistlichen im Alltag und Chordienst.",
        "clip_prompts": [
            "cassock soutane black clergy robe buttons, catholic priest wearing cassock"
        ]
    },

    # ================= 3. SAKRALE ARCHITEKTUR & KIRCHENAUSSTATTUNG =================
    {
        "id": "arch_hochaltar",
        "canonical": "Hochaltar",
        "category": "Sakrale Architektur",
        "synonyms": [
            "Choraltar", "Hauptaltar", "Altarretabel", "Altaraufsatz", "Flügelaltar", 
            "Barockaltar", "Altarbild", "Mensa", "Antependium"
        ],
        "iconclass": "11Q7141",
        "gnd": "4138356-4",
        "description": "Zentraler Hauptaltar im Chorhaupt der Kirche, oft monumental gestaltet.",
        "clip_prompts": [
            "ornate high altar baroque gothic church choir, gilded altarpiece reredos",
            "historical high altar with candles and crucifix"
        ]
    },
    {
        "id": "arch_zelebrationsaltar",
        "canonical": "Zelebrationsaltar",
        "category": "Sakrale Architektur",
        "synonyms": ["Volksaltar", "Tischaltar", "Gemeindealtar", "Freistehender Altar"],
        "iconclass": "11Q71411",
        "gnd": "4141998-3",
        "description": "Freistehender Altar zur Zelebration der Messe mit Blick zur Gemeinde (versus populum).",
        "clip_prompts": [
            "freestanding altar table in church nave sanctuary, celebration altar"
        ]
    },
    {
        "id": "arch_tabernakel",
        "canonical": "Tabernakel",
        "category": "Sakrale Architektur",
        "synonyms": [
            "Sakramentshaus", "Hostientresor", "Ziboriumaltar", "Tabernakeltür", "Gotteshaus"
        ],
        "iconclass": "11Q7143",
        "gnd": "4184317-4",
        "description": "Verschließbarer Schrein zur Aufbewahrung des Allerheiligsten (Hostien).",
        "clip_prompts": [
            "church tabernacle gilded safe on altar for eucharist, decorated tabernacle door"
        ]
    },
    {
        "id": "arch_kanzel",
        "canonical": "Kanzel",
        "category": "Sakrale Architektur",
        "synonyms": [
            "Predigtstuhl", "Ambo", "Schalldeckel", "Kanzelkorb", "Kanzeltreppe"
        ],
        "iconclass": "11Q7147",
        "gnd": "4029486-9",
        "description": "Erhöhter Platz im Kirchenraum zur Verkündigung des Evangeliums und Predigt.",
        "clip_prompts": [
            "carved church pulpit soundboard sounding board, historical wooden pulpit elevated",
            "priest preaching from ornate church pulpit"
        ]
    },
    {
        "id": "arch_taufbecken",
        "canonical": "Taufbecken",
        "category": "Sakrale Architektur",
        "synonyms": [
            "Taufstein", "Taufbrunnen", "Taufkapelle", "Piscina", "Baptisterium", "Taufkessel"
        ],
        "iconclass": "11Q73211",
        "gnd": "4129601-1",
        "description": "Becken für das Taufwasser zur Spendung des Sakraments der Taufe.",
        "clip_prompts": [
            "baptismal font stone carved baptism basin church, baptism font with bronze lid"
        ]
    },
    {
        "id": "arch_chorgestuehl",
        "canonical": "Chorgestühl",
        "category": "Sakrale Architektur",
        "synonyms": [
            "Chorsitz", "Miserikordien", "Kanonikersitze", "Stallen", "Klostersitze"
        ],
        "iconclass": "11Q7148",
        "gnd": "4147895-3",
        "description": "Reihe hölzerner Klappsitze im Altarraum für Priester, Domkapitel oder Mönche.",
        "clip_prompts": [
            "choir stalls carved wooden seats church sanctuary, monastic choir benches"
        ]
    },
    {
        "id": "arch_beichtstuhl",
        "canonical": "Beichtstuhl",
        "category": "Sakrale Architektur",
        "synonyms": ["Beichtzelle", "Beichtzimmer", "Beichtgitter", "Confessionale"],
        "iconclass": "11Q73241",
        "gnd": "4144360-3",
        "description": "Möbelstück mit Gittertrennwand zur Spendung des Beichtsakraments.",
        "clip_prompts": [
            "wooden confessional booth in church, ornate carved confessional box"
        ]
    },
    {
        "id": "arch_pieta",
        "canonical": "Pietà",
        "category": "Sakrale Architektur",
        "synonyms": [
            "Vesperbild", "Schmerzensmutter", "Maria mit totem Jesus", "Mater Dolorosa", "Marienklage"
        ],
        "iconclass": "11F73",
        "gnd": "4046048-4",
        "description": "Darstellung Marias mit dem Leichnam Jesu auf ihrem Schoß nach der Kreuzabnahme.",
        "clip_prompts": [
            "pieta statue mary holding body of jesus, carved church pietà sculpture"
        ]
    },
    {
        "id": "arch_kreuzweg",
        "canonical": "Kreuzweg",
        "category": "Sakrale Architektur",
        "synonyms": [
            "Kreuzwegstationen", "Via Dolorosa", "Kreuzwegtafeln", "Stationenweg", "Kalvarienberg"
        ],
        "iconclass": "73D4",
        "gnd": "4033095-3",
        "description": "14 bildliche Stationen des Leidensweges Jesu Christi von der Verurteilung bis zum Grab.",
        "clip_prompts": [
            "stations of the cross relief carved wall stations church, via dolorosa depictions"
        ]
    },
    {
        "id": "arch_orgelprospekt",
        "canonical": "Orgelprospekt",
        "category": "Sakrale Architektur",
        "synonyms": [
            "Kirchenorgel", "Pfeifenorgel", "Orgelgehäuse", "Spieltisch", "Orgelempore"
        ],
        "iconclass": "48C7331",
        "gnd": "4043844-2",
        "description": "Sichtbare Schauseite einer Pfeifenorgel auf der Kirchenempore.",
        "clip_prompts": [
            "church pipe organ gallery gilded pipes baroque organ facade",
            "historical church organ loft"
        ]
    },
    {
        "id": "arch_glockenstuhl",
        "canonical": "Glockenstuhl",
        "category": "Sakrale Architektur",
        "synonyms": [
            "Kirchenglocke", "Kirchengeläut", "Glockenturm", "Glockenweihe", "Kirchturmuhr"
        ],
        "iconclass": "11Q713",
        "gnd": "4157545-0",
        "description": "Tragwerk im Kirchturm für die Kirchenglocken.",
        "clip_prompts": [
            "church bells in belfry bronze church bell wooden bell frame, bell tower bells"
        ]
    },
    {
        "id": "arch_sakristei",
        "canonical": "Sakristei",
        "category": "Sakrale Architektur",
        "synonyms": ["Vasa-Raum", "Paramentenschrank", "Ankleideraum", "Sacristia"],
        "iconclass": "11Q7149",
        "gnd": "4178936-2",
        "description": "Nebenraum der Kirche zur Vorbereitung der Priester und Aufbewahrung der Vasa sacra.",
        "clip_prompts": [
            "church sacristy vestry antique vestment cabinets chalice chests"
        ]
    },

    # ================= 4. LITURGISCHE FEIERN & RITEN =================
    {
        "id": "rit_fronleichnam",
        "canonical": "Fronleichnamsprozession",
        "category": "Liturgische Feiern",
        "synonyms": [
            "Fronleichnam", "Theophorus", "Sakramentsträger", "Blumenteppich", 
            "Himmelsbaldachin", "Traghimmel", "Monstranzprozession", "Altäre im Freien"
        ],
        "iconclass": "11Q751",
        "gnd": "4155537-5",
        "description": "Fest des heiligsten Leibes und Blutes Christi mit feierlicher Monstranzprozession durch Straßen und Fluren.",
        "clip_prompts": [
            "corpus christi procession priest under canopy carrying monstrance, historical street procession flower carpet",
            "altar boys and priests in outdoor religious procession"
        ]
    },
    {
        "id": "rit_primiz",
        "canonical": "Primiz",
        "category": "Liturgische Feiern",
        "synonyms": [
            "Erste Heilige Messe", "Neupriester", "Primizfeier", "Primizsegen", "Primizkrone", "Primizpredigt"
        ],
        "iconclass": "11Q7326(+1)",
        "gnd": "4175697-1",
        "description": "Die erste heilige Messe eines neugeweihten katholischen Priesters in seiner Heimatgemeinde.",
        "clip_prompts": [
            "first solemn mass primiz young newly ordained priest flower crown, festive church service"
        ]
    },
    {
        "id": "rit_erstkommunion",
        "canonical": "Erstkommunion",
        "category": "Liturgische Feiern",
        "synonyms": [
            "Weißer Sonntag", "Erstkommunikanten", "Kommunionkinder", "Kommunionkerze", "Kommunionkleid"
        ],
        "iconclass": "11Q7323",
        "gnd": "4152988-1",
        "description": "Erster feierlicher Empfang der heiligen Kommunion durch Kinder in weißen Kleidern.",
        "clip_prompts": [
            "first holy communion children white dresses candles group photo church, first communicants"
        ]
    },
    {
        "id": "rit_firmung",
        "canonical": "Firmung",
        "category": "Liturgische Feiern",
        "synonyms": [
            "Firmsakrament", "Bischofsbesuch", "Chrisamsalbung", "Firmpaten", "Handauflegung", "Confirmata"
        ],
        "iconclass": "11Q7322",
        "gnd": "4017253-3",
        "description": "Sakrament der geistlichen Vollendung, gespendet vom Bischof durch Handauflegung und Chrisamsalbung.",
        "clip_prompts": [
            "catholic confirmation ceremony bishop anointing forehead chrism, church confirmation service"
        ]
    },
    {
        "id": "rit_priesterweihe",
        "canonical": "Priesterweihe",
        "category": "Liturgische Feiern",
        "synonyms": [
            "Ordination", "Weihemesse", "Prostration", "Bischöfliche Handauflegung", "Weiheliturgie"
        ],
        "iconclass": "11Q7326",
        "gnd": "4175659-4",
        "description": "Weihehandlung durch den Bischof mit Niederwerfen (Prostration) vor dem Altar.",
        "clip_prompts": [
            "ordination of catholic priests prostration on cathedral floor, bishop laying hands ordination"
        ]
    },
    {
        "id": "rit_maiandacht",
        "canonical": "Maiandacht",
        "category": "Liturgische Feiern",
        "synonyms": ["Marienfeier", "Marienlob", "Rosenkranzandacht", "Marienmonat"],
        "iconclass": "11Q752",
        "gnd": "4168621-4",
        "description": "Andacht im Mai zu Ehren der Gottesmutter Maria mit reichem Blumenschmuck.",
        "clip_prompts": [
            "marian devotion church floral decorated statue of virgin mary candles, evening prayer service"
        ]
    },
    {
        "id": "rit_karfreitag",
        "canonical": "Karfreitag",
        "category": "Liturgische Feiern",
        "synonyms": [
            "Kreuzverehrung", "Heiliges Grab", "Grablegung Christi", "Karwoche", "Karfreitagsliturgie"
        ],
        "iconclass": "73D6",
        "gnd": "4163339-3",
        "description": "Gedächtnis des Leidens und Sterbens Christi mit feierlicher Enthüllung und Verehrung des Kreuzes.",
        "clip_prompts": [
            "good friday veneration of the cross prostration priest liturgy, holy sepulchre holy grave display"
        ]
    },

    # ================= 5. KLERUS, ORDENSWESEN & ÄMTER =================
    {
        "id": "klerus_bischof",
        "canonical": "Bischof",
        "category": "Klerus & Ordenswesen",
        "synonyms": [
            "Weihbischof", "Diözesanbischof", "Erzbischof", "Oberhirte", "Pontifex", 
            "Bischofsporträt", "Bischofsinsignien", "Pektorale", "Bischofsring"
        ],
        "iconclass": "11P3111",
        "gnd": "4006949-7",
        "description": "Höchster geistlicher Würdenträger eines Bistums im bischöflichen Ornat.",
        "clip_prompts": [
            "catholic bishop wearing mitre miter crosier pectoral cross, bishop portrait pontifical vestments",
            "historical photograph of catholic bishop"
        ]
    },
    {
        "id": "klerus_domkapitular",
        "canonical": "Domkapitular",
        "category": "Klerus & Ordenswesen",
        "synonyms": [
            "Domherr", "Domdekan", "Dompropst", "Kathedralkapitel", "Kapitular", "Kanoniker"
        ],
        "iconclass": "11P3122",
        "gnd": "4150393-3",
        "description": "Priesterliches Mitglied des Domkapitels an einer Bischofskathedrale, oft mit Mozzetta und Brustkreuz.",
        "clip_prompts": [
            "cathedral canon capitular priest wearing mozzetta cape, senior catholic clergyman"
        ]
    },
    {
        "id": "klerus_pfarrer",
        "canonical": "Pfarrer",
        "category": "Klerus & Ordenswesen",
        "synonyms": [
            "Stadtpfarrer", "Priester", "Geistlicher", "Seelsorger", "Pfarrer i. R.", "Pastor", "Kuratus"
        ],
        "iconclass": "11P312",
        "gnd": "4045436-9",
        "description": "Leitender Seelsorger einer katholischen Pfarrgemeinde.",
        "clip_prompts": [
            "catholic parish priest pastor wearing cassock soutane roman collar, vintage priest photo"
        ]
    },
    {
        "id": "klerus_kaplan",
        "canonical": "Kaplan",
        "category": "Klerus & Ordenswesen",
        "synonyms": ["Vikar", "Kooperator", "Hilfspriester", "Jungpriester"],
        "iconclass": "11P3123",
        "gnd": "4163255-8",
        "description": "Junger Priester in den ersten Dienstjahren als Assistent des Pfarrers.",
        "clip_prompts": [
            "young assistant priest curate chaplain vicar cassock portrait"
        ]
    },
    {
        "id": "klerus_ministrant",
        "canonical": "Ministrant",
        "category": "Klerus & Ordenswesen",
        "synonyms": [
            "Messdiener", "Altarbube", "Altardiener", "Akolyt", "Ministranten", "Chorknabe"
        ],
        "iconclass": "11P314",
        "gnd": "4039499-2",
        "description": "Laienhelfer im Altarraum, gekleidet in Talar und Rochett (Chorhemd).",
        "clip_prompts": [
            "altar boys altar servers wearing cassock and surplice, children assisting at church altar"
        ]
    },
    {
        "id": "klerus_ordensschwester",
        "canonical": "Ordensschwester",
        "category": "Klerus & Ordenswesen",
        "synonyms": [
            "Nonne", "Ordensfrau", "Klosterschwester", "Barmherzige Schwester", "Habit", 
            "Schleier", "Haube", "Ordensgewand", "Krankenschwester Orden"
        ],
        "iconclass": "11P3152",
        "gnd": "4075594-0",
        "description": "Mitglied einer weiblichen Ordensgemeinschaft in traditioneller Ordenstracht mit Schleier.",
        "clip_prompts": [
            "catholic nun sister wearing traditional habit veil wimple rosary, vintage nun portrait"
        ]
    },
    {
        "id": "klerus_franziskaner",
        "canonical": "Franziskaner",
        "category": "Klerus & Ordenswesen",
        "synonyms": ["Kapuziner", "Minoriten", "Bettelorden", "Franziskanermönch", "Brauner Habit", "Kordel"],
        "iconclass": "11P3151(FRANCISCAN)",
        "gnd": "4018253-1",
        "description": "Mönch des Franziskanerordens im braunen Wollgewand mit Kapuze und weißem Strick (Kordel).",
        "clip_prompts": [
            "franciscan friar monk brown habit rope cincture sandaled feet, vintage monk portrait"
        ]
    },
    {
        "id": "klerus_benediktiner",
        "canonical": "Benediktiner",
        "category": "Klerus & Ordenswesen",
        "synonyms": ["OSB", "Benediktinermönch", "Schwarzer Habit", "Kukulle", "Klostermönch"],
        "iconclass": "11P3151(BENEDICTINE)",
        "gnd": "4005485-6",
        "description": "Mönch der ältesten abendländischen Ordensgemeinschaft im schwarzen Habit mit Skapulier.",
        "clip_prompts": [
            "benedictine monk black habit scapular cowl monastery library, catholic monk"
        ]
    },
    {
        "id": "klerus_jesuiten",
        "canonical": "Jesuiten",
        "category": "Klerus & Ordenswesen",
        "synonyms": ["SJ", "Societas Jesu", "Jesuitenorden", "Jesuitenpater"],
        "iconclass": "11P3151(JESUIT)",
        "gnd": "4028567-4",
        "description": "Mitglied der Gesellschaft Jesu (gegründet von Ignatius von Loyola).",
        "clip_prompts": [
            "jesuit priest father cassock black cloak, society of jesus portrait"
        ]
    }
]
