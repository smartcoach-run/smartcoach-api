"""
rules_service.py
---------------------------------------------------------------------
Service contenant les règles métier statiques utilisées par SCN_1.

CONFORME :
- RCTC
- Manuel SmartCoach
- Story SCN_1
- Champs Airtable réels (aucune invention)

Ce module contient uniquement :
- Des règles statiques
- Des constantes utilisées par SCN_1
- Une fonction de résolution de clé de niveau

AUCUNE validation ici (c’est le rôle du scenario ou d’un module dédié).
---------------------------------------------------------------------
"""

class RulesService:

    def __init__(self):
        """
        Initialise les règles statiques utilisées par SCN_1.
        Ces règles sont figées et cohérentes avec le RCTC.
        """

        # --------------------------------------------------------------
        # RÈGLE 1 : Mapping des niveaux → clés référence
        # --------------------------------------------------------------
        # Ces clés sont EXACTEMENT celles du RCTC et du Google Sheet
        # utilisé par Airtable pour créer le champ :
        #   "Clé niveau référence"
        #
        # NE PAS MODIFIER SANS METTRE À JOUR RCTC
        # --------------------------------------------------------------
        self.cle_niveau_reference = {
            "Débutant": "N1",
            "Intermédiaire": "N2",
            "Avancé": "N3",
            "Expert": "N4",
        }

        # --------------------------------------------------------------
        # RÈGLE 2 : Nombre de semaines recommandé par objectif
        # --------------------------------------------------------------
        # Correspond au Manuel et RCTC :
        # - 5K → 6 à 8 semaines
        # - 10K → 8 à 10 semaines
        # - Semi → 10 à 12 semaines
        # - Marathon → 14 à 16 semaines
        # --------------------------------------------------------------
        self.durees_objectifs = {
            "5K": 8,
            "10K": 10,
            "Semi-marathon": 12,
            "Marathon": 16
        }

        # --------------------------------------------------------------
        # RÈGLE 3 : Nombre minimal de jours disponibles selon le niveau
        # --------------------------------------------------------------
        # Sert à générer les bons messages dans SCN_1
        # --------------------------------------------------------------
        self.min_jours_par_niveau = {
            "Débutant": 2,
            "Intermédiaire": 3,
            "Avancé": 4,
            "Expert": 4
        }

        # --------------------------------------------------------------
        # RÈGLE 4 : Nombre minimal de séances hebdo selon niveau
        # (Aligné avec CONFIG_TYPES dans le Sheet)
        # --------------------------------------------------------------
        self.min_seances_par_niveau = {
            "Débutant": 2,
            "Intermédiaire": 3,
            "Avancé": 4,
            "Expert": 5
        }


    # ==================================================================
    # MÉTHODES PUBLIQUES
    # ==================================================================

    def resolve_cle_niveau(self, niveau: str) -> str | None:
        """
        Retourne la clé de niveau pour un niveau donné.
        Ex : "Intermédiaire" → "N2"

        PARAMÈTRES
        ----------
        niveau : str
            Niveau du coureur (champ Airtable : "Niveau_normalisé")

        RETOUR
        ------
        str | None
            Identifiant de niveau ou None si non trouvé
        """
        return self.cle_niveau_reference.get(niveau)


    def get_duree_objectif(self, objectif: str) -> int | None:
        """
        Retourne la durée du plan recommandée pour un objectif donné.

        PARAMÈTRES
        ----------
        objectif : str
            Objectif course (champ Airtable : "Objectif_normalisé")

        RETOUR
        ------
        int | None
        """
        return self.durees_objectifs.get(objectif)


    def get_min_jours(self, niveau: str) -> int | None:
        """
        Retourne le nombre minimum de jours de course selon le niveau.
        """
        return self.min_jours_par_niveau.get(niveau)


    def get_min_seances(self, niveau: str) -> int | None:
        """
        Retourne le nombre minimum de séances hebdo selon le niveau.
        """
        return self.min_seances_par_niveau.get(niveau)
