🎯 Objectif du document

Ce document fige l’état stable du moteur SmartCoach après validation complète de :

SCN_6 (orchestrateur)

SC-001 (Running – progression structurée)

SC-002 (Running – plaisir / reprise adulte)

SCN_0g V1 (générateur legacy)

Suite de tests QA SCN_6 (local + Fly)

Il sert de référence de non-régression avant toute évolution.

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

🧭 Prochaines évolutions (HORS PÉRIMÈTRE ACTUEL)

organisation globale des validations QA (CI, regroupement)

bascule vers scn_0g_vNext

enrichissement SC-002

ajout scénarios Vitalité / Kids / Hyrox

📌 Aucune de ces évolutions ne doit casser SC-001 / SC-002.