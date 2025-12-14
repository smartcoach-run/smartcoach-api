🧠 SmartCoach — Moteur de scénarios (README)
🎯 Objectif

Ce document fige les invariants fonctionnels et techniques du moteur SmartCoach après stabilisation de SCN_6, SC-001, SC-002 et SCN_0g V1.

Il sert de point de repère pour :

éviter les régressions,

comprendre rapidement le rôle de chaque composant,

préparer les évolutions (vNext) sans casser l’existant.

🧩 Vue d’ensemble
Entrée (Make / Postman / API)
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
🔹 SCN_6 — Orchestrateur

Point d’entrée principal du moteur

Responsabilités :

extraction explicite du run_context

scoring multi-scénarios

sélection déterministe du scénario

préparation du contexte pour le générateur

❌ Ne lit pas Airtable directement

🔹 SC-001 — Running progression structurée

Cas d’usage :

marathon / objectif chrono

Signaux clés :

mode = running

objectif marathon

chrono cible compatible

Toujours conservé pour non-régression

🔹 SC-002 — Running plaisir / reprise adulte

Cas d’usage :

reprise, plaisir, vitalité

Clé pivot :

objectif_normalisé = RUN_PLAISIR

Génère des séances simples, EF, non chronométrées

🔹 SCN_0g V1 — Générateur minimal (legacy)

Génère une séance minimale à partir d’un slot

Lit exclusivement :

context.payload["slot"]


Ne lit PAS :

context.slot_date

context.slot_id

Aucune dépendance externe

Version figée (V1)

🔹 SCN_0g vNext — Cible future

Version context-first

Lira directement :

context.slot_date
context.type_cible
context.profile


Supprimera le besoin du payload legacy

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
    "type": "distance | temps | null",
    "time": "HH:MM:SS | null"
  },
  "objectif_normalisé": "RUN_PLAISIR | RUN_M | ..."
}


👉 Règle : SCN_6 ne reconstruit pas l’intention métier.
Elle est fournie en amont (Airtable / Make).

🔑 Invariants métier (à ne pas casser)

🔒 objectif_normalisé

clé pivot entre Airtable et moteur

détermine le scénario

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

🧪 Tests de référence (non-régression)

Deux cas doivent toujours fonctionner :

✅ SC-001 — Marathon / progression structurée

✅ SC-002 — Running plaisir / reprise

Toute évolution qui casse l’un de ces deux tests doit être stoppée.

🧭 Prochaines évolutions prévues

Bascule vers scn_0g_vNext (suppression du payload legacy)

Enrichissement de SC-002 (volume, progressivité douce)

Ajout de nouveaux scénarios (Vitalité, Kids, Hyrox)