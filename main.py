# main.py (v0)
# Point d'entrée minimal pour exécuter SCN_1 en local.

import argparse
from core.context import SmartCoachContext
from scenarios.dispatcher import dispatch_scenario


def parse_arguments():
    """
    Parse les arguments CLI.
    Exemple :
      python main.py --scn SCN_1 --record TEST01
    """
    parser = argparse.ArgumentParser(description="SmartCoach CLI - v0")
    parser.add_argument("--scn", required=True, help="Nom du scénario à exécuter (ex: SCN_1)")
    parser.add_argument("--record", required=True, help="record_id (ex: TEST01)")
    return parser.parse_args()


def main():
    args = parse_arguments()

    # 1. Construire le contexte minimal
    context = SmartCoachContext(record_id=args.record)

    # 2. Exécuter le scénario
    result = dispatch_scenario(args.scn, context)

    # 3. Afficher résultat
    print("\n=== SmartCoach - Résultat ===")
    print(f"Status     : {result.status}")
    print(f"Messages   : {result.messages}")
    print(f"Données    : {result.data}")
    print("=============================\n")


if __name__ == "__main__":
    main()
