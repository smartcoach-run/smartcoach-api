🎯 Objectif du document

📌 Statut du document — POINT ZÉRO MVP

Ce document fige l’état du moteur SmartCoach après un audit complet
(runtime, scénarios, data, QA, intégration).

L’architecture, les contrats et les responsabilités décrits ici sont
considérés comme STABLES pour la phase MVP.

Toute évolution ultérieure devra être motivée par un usage réel
et validée explicitement.


Ce document fige l’état stable du moteur SmartCoach après validation complète de :

SCN_6 (orchestrateur)

SC-001 (Running – progression structurée)

SC-002 (Running – plaisir / reprise adulte)

SCN_0g V1 (générateur legacy)

Suite de tests QA SCN_6 (local + Fly)

Il sert de référence de non-régression avant toute évolution.

🗂️ Organisation du projet (repères)

🔵 Runtime & orchestration

Décision, exécution, enchaînement des scénarios

scn_6.py — orchestrateur décisionnel principal

dispatcher.py — routage des scénarios

scn_run.py — adaptateur vers le moteur externe

api.py — exposition FastAPI

🔵 Génération & socle métier

Génération concrète des séances

scn_0g.py — socle EF (actif)

scn_2.py — génération séance running

bab_engine_mvp.py — sélection finale de séance

🔵 Données & normalisation

Accès Airtable et préparation des données

airtable_fields.py — dictionnaire de champs

airtable_service.py — accès Airtable

extractors.py, validators.py, selectors.py

🟣 QA & diagnostic

Tests, non-régression, introspection

selftest.py

registry_scn_6.py

war_room.py

🟡 Utilitaires / sorties

Hors moteur décisionnel

ics_builder.py

router.py (ICS)

logger.py

🟡 Génération ICS (STABLE — CONTRAT MVP)

La génération ICS fait partie des sorties utilitaires du moteur SmartCoach.

Elle est hors moteur décisionnel et hors orchestration métier.

Principe fondamental

1 séance générée = 1 fichier ICS

1 ICS = 1 événement calendrier (VEVENT)

Il n’existe aucune génération batch ou multi-séances au stade MVP

Source de vérité

L’ICS est généré exclusivement à partir de :

data.session


produit par SCN_6.

Aucune autre partie de la réponse n’est lue ou interprétée :

❌ war_room

❌ scores

❌ phase_context

❌ logique métier implicite

Responsabilités

ics_builder.py :

transforme une session SmartCoach en événement calendrier

n’applique aucune règle métier

n’effectue aucune décision

router.py (ICS) :

expose l’endpoint de génération

enrichit éventuellement avec des données contextuelles simples (ex. lieu)

ne modifie jamais la session

Contenu de l’événement ICS

L’événement calendrier inclut, si disponibles :

titre SmartCoach

date et durée (timezone Europe/Paris)

déroulé de la séance (blocks ou steps)

intensité

phase

messages du coach

alarmes calendrier

Invariants ICS (à ne jamais casser)

timezone explicite Europe/Paris

1 session → 1 UID stable

aucune logique de génération de séance

aucun appel moteur depuis l’ICS

l’ICS est idempotent et reproductible

🔴 Legacy (hors trajectoire)

Conservé à titre d’archive, non utilisé par le moteur actuel

providers monolithiques

modèles riches non intégrés

adaptateurs historiques

(sans forcément lister tous les fichiers)

🧠 Pourquoi cette forme est la bonne

✔️ lisible en 1 minute

✔️ stable dans le temps

✔️ ne casse pas si un fichier bouge

✔️ empêche les mauvaises réintroductions

✔️ complète parfaitement le contrat runtime

👉 C’est une carte mentale, pas un inventaire comptable.

🧭 Règle d’or à retenir

Si un développeur a besoin de plus de 2 lignes pour comprendre un fichier,
ce n’est pas au README de le faire.

🧩 Vue d’ensemble (architecture stabilisée)
Entrée (Make / Postman / QA API)
            ↓
          SCN_6
      (orchestrateur)
            ↓
     Sélection SC-00x
            ↓
         SCN_0g
     (génération séance)
            ↓
   Résultat + Airtable

🧠 Rôle des composants
🔹 SCN_6 — Orchestrateur (STABLE)

Point d’entrée principal du moteur.

Responsabilités :

extraction explicite du run_context

scoring multi-scénarios

sélection déterministe du scénario

calcul du type_cible

préparation du contexte pour le générateur

Invariants :

❌ ne lit pas Airtable

❌ ne reconstruit pas l’intention métier

✅ consomme un contexte déjà normalisé

🔹 SC-001 — Running / progression structurée (RÉFÉRENCE)

Cas d’usage :

préparation marathon

objectif chronométré

Signaux clés :

mode = running

objective_type = marathon

chrono cible compatible

tranche d’âge cohérente

Statut :

test de non-régression absolu

toute évolution qui casse SC-001 est bloquante

🔹 SC-002 — Running plaisir / reprise adulte (RÉFÉRENCE)

Cas d’usage :

reprise douce

plaisir / vitalité

absence d’objectif chrono

Clé pivot :

objectif_normalisé = RUN_PLAISIR

Comportement :

séances simples

endurance fondamentale

logique non chronométrée

Statut :

test de non-régression absolu

scénario socle pour extensions futures (Vitalité, Santé, etc.)

🔹 SCN_0g V1 — Générateur legacy (FIGÉ)

Rôle :

génération minimale d’une séance à partir d’un slot

Lit exclusivement :

context.payload["slot"]


Ne lit pas :

context.slot_date

context.slot_id

context.profile

Contraintes :

aucune dépendance externe

comportement figé

utilisé uniquement via SCN_6

🔹 SCN_0g vNext — Cible future (NON ACTIVE)

Évolutions prévues :

lecture directe du contexte

suppression du payload legacy

génération plus riche et adaptative

Statut :

non utilisée

ne doit pas être appelée en production

📥 Contrat d’entrée — run_context (INVARIANT)

SCN_6 consomme un contexte déjà normalisé :

{
  "slot": {
    "slot_id": "string",
    "date": "YYYY-MM-DD"
  },
  "profile": {
    "mode": "running | vitalité | kids | hyrox",
    "submode": "string",
    "age": number
  },
  "objective": {
    "type": "distance | temps | marathon | null",
    "time": "HH:MM:SS | null"
  },
  "objectif_normalisé": "RUN_PLAISIR | M | ..."
}


📌 Règle d’or

SCN_6 ne reconstruit jamais l’intention métier
Elle est fournie en amont (Airtable / Make).

🔑 Invariants métier (à ne jamais casser)
🔒 objectif_normalisé

clé pivot Airtable ↔ moteur

détermine le scénario

source de vérité

🔒 type_cible

seule donnée métier persistée côté Slot

ex : E, I, T

🔒 model_family

décision interne moteur

❌ jamais persistée dans Airtable

⚠️ Pont legacy assumé (SCN_6 → SCN_0g V1)

Pour compatibilité avec SCN_0g V1, SCN_6 injecte :

context.payload = {
  "slot": {
    "slot_id": context.slot_id,
    "date": context.slot_date,
    "type": context.type_cible
  }
}


📌 Cette duplication est :

volontaire

temporaire

documentée

👉 À supprimer lors de la bascule vers scn_0g_vNext.

🧪 Validation & QA (NOUVEAU – STABLE)
✔️ Tests de référence

Deux scénarios doivent toujours passer :

✅ SC-001 — Marathon / progression structurée

✅ SC-002 — Running plaisir / reprise

✔️ Suite QA SCN_6 (API)

Un endpoint dédié permet d’exécuter tous les scénarios de test en une fois :

GET /qa/run/scn_6


Retour type :

{
  "success": true,
  "suite": "SCN_6",
  "summary": {
    "total": 2,
    "passed": 2,
    "failed": 0
  },
  "results": [
    { "test_id": "SCN_6_SC001", "status": "PASSED" },
    { "test_id": "SCN_6_SC002", "status": "PASSED" }
  ]
}


✔️ Validé :

en local

sur Fly.io

📌 Code legacy / hors trajectoire

Certains fichiers identifiés lors de l’audit (providers monolithiques,
modèles riches non utilisés, adaptateurs historiques) sont volontairement
hors trajectoire du moteur actuel.

Ils sont conservés à titre d’archive ou de référence, mais ne doivent
pas être réintroduits dans le runtime SmartCoach.


🧭 Prochaines évolutions (HORS PÉRIMÈTRE ACTUEL)

organisation globale des validations QA (CI, regroupement)

bascule vers scn_0g_vNext

enrichissement SC-002

ajout scénarios Vitalité / Kids / Hyrox

📌 Aucune de ces évolutions ne doit casser SC-001 / SC-002.

📘 Contrat de données SmartCoach (RÉFÉRENCE OFFICIELLE)

Ce document définit le contrat de données officiel entre :

Make / Airtable (amont)

l’API SmartCoach

les scénarios moteur (SCN_6, SCN_0g)

Toute évolution d’un payload, d’un contexte ou d’un champ doit être validée ici.

🔹 1. Principe général

Le moteur SmartCoach est déterministe

Il ne reconstruit jamais l’intention métier

Toute décision repose sur un contexte fourni en amont

👉 Un JSON valide n’implique pas un contexte valide.

🔹 2. Contexte moteur de référence : run_context
Ce contrat est rappelé ici comme référence officielle et unique.
SCN_6 consomme exclusivement le contexte suivant :

{
  "slot": {
    "slot_id": "string",          // OBLIGATOIRE
    "date": "YYYY-MM-DD"          // OBLIGATOIRE
  },
  "profile": {
    "mode": "running | vitalité | kids | hyrox",   // OBLIGATOIRE
    "submode": "string",                           // optionnel
    "age": number,                                 // OBLIGATOIRE
    "level": "debutant | intermediaire | avance"   // OBLIGATOIRE (Phase 2+)
  }
  "objective": {
    "type": "distance | temps | marathon | null",  // optionnel
    "time": "HH:MM:SS | null"                       // optionnel
  },
  "objectif_normalisé": "RUN_PLAISIR | M | ..."    // OBLIGATOIRE
}

🔹 3. Champs obligatoires (INVARIANTS)

Sans ces champs, le moteur fonctionne mais refuse de décider :

slot.slot_id

slot.date

profile.mode

profile.age

objectif_normalisé

profile.level

🔹 4. Champs optionnels

profile.submode

objective.type

objective.time

Ils enrichissent la décision mais ne sont pas bloquants.

🔹 5. Champs internes moteur (NE PAS FOURNIR)

Ces champs sont :

produits par le moteur

non persistés

non contractuels

Exemples :

model_family

scores

war_room

phase_context

🔹 6. SOCLE — SCN_0g
SCN_0g V1 (ACTIF)

Contrat minimal

Génère une séance à partir de :

{
  "slot": {
    "slot_id": "string",
    "date": "YYYY-MM-DD",
    "type": "E | T | …"
  }
}

SCN_0g vNext (DÉSACTIVÉ)

Réactivation possible uniquement si :

le contrat run_context est figé

model_family est toujours présent

SCN_6 est l’unique point d’entrée moteur

🔹 7. Règle de gouvernance (GARDE-FOU)

Avant toute évolution :

modification de payload Make

ajout de champ

enrichissement de scénario

👉 Vérifier et mettre à jour ce contrat en premier.

SCENARIOS MAKE 

SCN_0a_V2 – Rôle

Accueil immédiat utilisateur après Fillout.
Envoi d’un message de bienvenue personnalisé via le moteur SmartCoach.

Contrat d’entrée

champs attendus

format

Contrat moteur

endpoint

payload

réponse attendue

🟠 Orchestration Make — CORE_1 / CORE_2 (STABLE)

Le moteur SmartCoach est orchestré par deux scénarios Make distincts, aux responsabilités strictement séparées.

CORE_1 — Bootstrap du plan (STABLE)

Rôle :

déclenchement initial après validation utilisateur

génération de la première séance

création du premier slot

Caractéristiques :

appelé une seule fois par plan

peut générer une session avant la création du slot

initialise session_id sur le slot

Statut :

scénario de bootstrap

asymétrie slot / session assumée

ne doit pas être appelé en boucle

CORE_2 — Cycle de vie du plan (STABLE)

Rôle :

traitement des slots planifiés

génération des séances suivantes

envoi ICS

création du slot suivant

Règles invariantes :

ne traite que les slots avec :

status = pending

session_id vide

ne crée jamais de session lors de la création d’un slot

crée un slot après envoi de l’ICS

garantit : 1 slot → 1 session → 1 ICS

Sécurité :

idempotent

relançable sans double génération

protégé contre les retries Make / HTTP

🔒 Invariants d’orchestration (à ne jamais casser)

slot_id = Record ID Airtable

session_id est créé uniquement par generate_session

un slot peut exister sans session

un slot avec session_id ne doit jamais être retraité

Chaque séance générée par le moteur inclut un champ `decision_trace`
décrivant explicitement le raisonnement moteur.
decision_trace: {
  inputs: {
    level,
    phase,
    seance_type,
    objectif,
    engine_version — champ interne moteur, optionnel
  },
  rules_applied: [
    { id, label, scope }
  ],
  arbitrations: [
    { id, decision, value, unit?, reason }
  ],
  safety_checks: [ string ],
  final_choice: {
    block_id,
    reason
  }
}

La Phase 3 introduira des mécanismes d’adaptation du moteur
basés sur des signaux explicites (feedback, charge, progression).

Principes non négociables :
- aucune adaptation implicite
- toute adaptation génère une nouvelle decision_trace
- les règles d’adaptation sont nommées et traçables
- SCN_6 reste orchestrateur uniquement

RG_MEM_001 — FATIGUE_PERSISTENCE (P3-E)

Description:
Le moteur ne réagit pas à un signal isolé de fatigue.
Il consolide les feedbacks récents sur une fenêtre courte (J-1 / J-2)
afin d’éviter les sur-réactions.

Fenêtre:
- 2 dernières séances maximum
- Feedbacks valides < 72h

Règles:
- 2× fatigued consécutifs → fatigue persistante
- 1× fatigued + 1× neutral → maintien
- good efface toute fatigue précédente

Impact:
- Production d’un adaptive_context consolidé
- Aucune logique d’adaptation directe dans SCN_2
