<!-- admin_header.html -->
<header class="admin-page-header-bar">
    <div class="container">
        <div class="flex items-center space-x-4">
             <a href="admin_dashboard.html" id="back-to-dashboard-button" class="btn btn-admin-secondary btn-sm flex items-center hidden">
                <i class="fas fa-arrow-left mr-2"></i>
                Retour au Tableau de Bord
            </a>
            <div id="admin-header-title-area">
                 <h1>Maison Trüvra - Admin</h1>
            </div>
        </div>
        <div class="flex items-center space-x-4">
            <span id="admin-user-greeting" class="text-sm mr-2">Bonjour, Admin!</span>
            <button id="admin-logout-button" class="btn btn-admin-danger btn-sm flex items-center">
                <i class="fas fa-sign-out-alt mr-2"></i>Déconnexion
            </button>
        </div>
    </div>
</header>

<nav class="admin-main-nav">
    <div class="container">
        <div class="nav-links-container">
            <a href="admin_dashboard.html" class="admin-nav-link" data-page="admin_dashboard.html">Tableau de Bord</a>
            <a href="admin_manage_products.html" class="admin-nav-link" data-page="admin_manage_products.html">Produits</a>
            <a href="admin_manage_inventory.html" class="admin-nav-link" data-page="admin_manage_inventory.html">Inventaire</a>
            <a href="admin_view_inventory.html" class="admin-nav-link" data-page="admin_view_inventory.html">Voir Inventaire</a>
            <a href="admin_manage_orders.html" class="admin-nav-link" data-page="admin_manage_orders.html">Commandes</a>
            <a href="admin_manage_users.html" class="admin-nav-link" data-page="admin_manage_users.html">Utilisateurs</a>
            <a href="admin_manage_categories.html" class="admin-nav-link" data-page="admin_manage_categories.html">Catégories</a>
            <a href="admin_invoices.html" class="admin-nav-link" data-page="admin_invoices.html">Factures</a>
            <a href="admin_manage_reviews.html" class="admin-nav-link" data-page="admin_manage_reviews.html">Avis</a>
            <a href="admin_profile.html" class="admin-nav-link" data-page="admin_profile.html">Mon Profil</a>
            <!-- Add other common admin navigation links here -->
        </div>
    </div>
</nav>
