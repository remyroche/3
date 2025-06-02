# Maison Trüvra E-Commerce Project

Maison Trüvra is a Flask and JavaScript-based e-commerce web application designed for selling truffles and related luxury food products. This project includes a backend API for managing products, inventory, users, orders, and newsletter subscriptions, as well as a frontend website for customer interaction.


## Project Structure
maison-truvra-project/
├── backend/                    # Flask backend application
│   ├── auth/                   # Authentication blueprint
│   ├── inventory/              # Inventory management blueprint
│   ├── newsletter/             # Newsletter subscription blueprint
│   ├── orders/                 # Order processing blueprint
│   ├── products/               # Product management blueprint
│   ├── static/                 # (Optional) Static files for backend if any
│   ├── templates/              # (Optional) Templates for backend if any
│   ├── init.py             # Application factory
│   ├── config.py               # Configuration settings
│   ├── database.py             # Database initialization and helpers
│   └── run.py                  # Script to run the Flask development server
│   └── utils.py                # Backend utility functions
├── website/                    # Frontend HTML, CSS, JS
│   ├── css/                    # (Optional) Custom CSS files
│   ├── images/                 # Static images for the website (e.g., logo)
│   ├── js/                     # (Could move scripts.js here)
│   │   └── scripts.js          # Main JavaScript file for frontend logic
│   ├── index.html
│   ├── nos-produits.html
│   ├── produit-detail.html
│   ├── panier.html
│   ├── compte.html
│   ├── paiement.html           # Checkout page
│   ├── confirmation-commande.html # Order confirmation page
│   └── ... (other HTML pages)
├── output_test_labels/         # Example output directory for generate_label.py
├── output_test_passports/      # Example output directory for generate_passport_html.py
├── maison_truvra.db            # SQLite database file (created by backend)
├── generate_label.py           # Script to generate product labels
├── generate_passport_html.py   # Script to generate HTML product passports
├── utils.py                    # Shared utility functions (e.g., for date formatting)
├── requirements.txt            # Python dependencies
└── README.md


## Setup and Installation

**Prerequisites:**
* Python 3.7+
* pip (Python package installer)

**1. Clone the Repository:**
   ```bash
   git clone <repository-url>
   cd maison-truvra-project

