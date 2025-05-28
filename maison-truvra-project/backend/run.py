# backend/run.py
# Ce script est utilisé pour démarrer l'application Flask.

from . import create_app # Importation relative de la factory create_app depuis __init__.py du package backend

# Crée une instance de l'application en utilisant la factory.
# Cela permet de s'assurer que l'application est configurée correctement avant d'être exécutée.
app = create_app()

if __name__ == '__main__':
    # Récupérer le port depuis les variables d'environnement ou utiliser 5001 par défaut
    # Cela permet plus de flexibilité, notamment pour le déploiement.
    port = int(app.config.get("PORT", 5001))
    
    # app.run() est utilisé pour le serveur de développement Flask.
    # Ne pas utiliser en production. Pour la production, un serveur WSGI comme Gunicorn ou uWSGI est recommandé.
    # Le mode debug est contrôlé par app.config['DEBUG'] qui est défini dans config.py.
    app.run(host='0.0.0.0', port=port, debug=app.config['DEBUG'])
