// Global variables for data
let allProductsData = null;
let allCategoriesData = null;

document.addEventListener('DOMContentLoaded', async () => {
    // utils.js should have already initialized currentLang

    // Fetch data once
    // Ensure correct paths to your JSON files
    allProductsData = await fetchData('../data/products_details.json'); 
    allCategoriesData = await fetchData('../data/categories_details.json');

    const mainContainer = document.getElementById('nos-produits-main-container'); // Assuming this is your main content area

    if (!mainContainer) {
        console.error('Main container (#nos-produits-main-container) not found on nos_produits.html');
        return;
    }

    if (!allProductsData || !allCategoriesData) {
        mainContainer.innerHTML = `<p>${getTranslatedText({error: {fr: "Erreur critique: Impossible de charger les données.", en: "Critical Error: Could not load data."}}, 'error')}</p>`;
        return;
    }

    // Handle routing based on URL parameters on initial load and on popstate (back/forward)
    window.addEventListener('popstate', renderPageContent);
    renderPageContent(); // Initial render
});

function renderPageContent() {
    const params = new URLSearchParams(window.location.search);
    const productId = params.get('id');
    const urlLang = params.get('lang');

    // Update language if specified in URL and different from current
    if (urlLang && ['fr', 'en'].includes(urlLang) && urlLang !== currentLang) {
        setLanguage(urlLang); // This updates currentLang in utils.js
        // The page will typically reload if setLanguageAndReload is used,
        // or if not, ensure UI updates if language change affects non-dynamic text.
    }

    const mainContainer = document.getElementById('nos-produits-main-container');
    if (!mainContainer) return;

    if (productId) {
        displaySingleProductDetails(productId, mainContainer);
    } else {
        displayProductList(mainContainer);
    }
}

function displayProductList(container) {
    container.innerHTML = ''; // Clear previous content or loading message

    const productListWrapper = document.createElement('div');
    productListWrapper.id = 'product-list-container'; // Retain for styling
    // Example: Add Tailwind classes for a grid layout
    productListWrapper.className = 'grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6';


    if (Object.keys(allProductsData).length === 0) {
        productListWrapper.innerHTML = `<p>${getTranslatedText({empty: {fr: "Aucun produit à afficher.", en: "No products to display."}}, 'empty')}</p>`;
        container.appendChild(productListWrapper);
        return;
    }

    for (const productId in allProductsData) {
        const product = allProductsData[productId];
        const category = allCategoriesData[product.category_id] || {};

        const productCard = document.createElement('div');
        // Example: Tailwind classes for product cards
        productCard.className = 'product-card bg-white shadow-xl hover:shadow-2xl transition-shadow duration-300 rounded-lg overflow-hidden flex flex-col';

        const productName = getTranslatedText(product, 'name');
        const productDescriptionShort = getTranslatedText(product, 'description_short');
        const categoryName = getTranslatedText(category, 'name');
        const productUnit = getTranslatedText(product, 'unit');

        // Link to the detail view on the same page by updating URL parameters
        const detailUrl = `?id=${productId}&lang=${currentLang}`; // Relative URL for the current page

        productCard.innerHTML = `
            <img src="${product.image_url || '../images/placeholder.png'}" alt="${productName}" class="w-full h-56 object-cover">
            <div class="p-5 flex flex-col flex-grow">
                <h3 class="text-xl font-semibold text-gray-800 mb-2">${productName}</h3>
                <p class="text-xs text-gray-500 mb-1 italic">${categoryName}</p>
                <p class="text-gray-600 text-sm mb-3 flex-grow">${productDescriptionShort}</p>
                <p class="text-lg font-bold text-indigo-600 mb-4">${product.price_eur.toFixed(2)} € ${productUnit}</p>
                <a href="${detailUrl}" class="mt-auto block w-full text-center bg-indigo-500 hover:bg-indigo-700 text-white font-semibold py-2 px-4 rounded-md transition-colors duration-300">
                    ${getTranslatedText({details: {fr: "Voir détails", en: "View Details"}}, 'details')}
                </a>
            </div>
        `;
        productListWrapper.appendChild(productCard);
    }
    container.appendChild(productListWrapper);
}

function displaySingleProductDetails(productId, container) {
    container.innerHTML = ''; // Clear previous content (e.g., product list)

    const product = allProductsData[productId];
    if (!product) {
        container.innerHTML = `<p>${getTranslatedText({error: {fr: "Produit non trouvé.", en: "Product not found."}}, 'error')}</p>`;
        return;
    }
    const category = allCategoriesData[product.category_id] || {};

    // "Back to list" button - links to the page without 'id' parameter
    const backLinkUrl = `?lang=${currentLang}`; // Relative URL for the current page
    const backButtonHtml = `
        <a href="${backLinkUrl}" class="inline-block bg-gray-200 hover:bg-gray-300 text-gray-700 font-semibold py-2 px-4 rounded-md mb-6 transition-colors duration-300">
            &larr; ${getTranslatedText({back: {fr: "Retour à la liste", en: "Back to list"}}, 'back')}
        </a>`;

    const detailWrapper = document.createElement('div');
    detailWrapper.id = 'product-detail-content'; // For specific styling if needed

    // Product Info
    const productName = getTranslatedText(product, 'name');
    const productDescLong = getTranslatedText(product, 'description_long');
    const productUnit = getTranslatedText(product, 'unit');

    // Category Info
    const categoryName = getTranslatedText(category, 'name');
    const categoryDesc = getTranslatedText(category, 'description');
    // ... (get all other category fields as in your original produit-detail.js)
    const categorySpecies = getTranslatedText(category, 'species');
    const categoryMainIngredients = getTranslatedText(category, 'main_ingredients');
    const categoryIngredientsNotes = getTranslatedText(category, 'ingredients_notes');
    const categoryFreshPreserved = getTranslatedText(category, 'fresh_vs_preserved');
    const categorySizeDetails = getTranslatedText(category, 'size_details');
    const categoryPairings = getTranslatedText(category, 'pairings');
    const categoryWeightInfo = getTranslatedText(category, 'weight_info');
    const categoryNotes = getTranslatedText(category, 'category_notes');

    detailWrapper.innerHTML = `
        ${backButtonHtml}
        <article class="bg-white p-6 md:p-8 rounded-lg shadow-xl">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-8 items-start">
                <div>
                    <img src="${product.image_url || '../images/placeholder.png'}" alt="${productName}" class="w-full h-auto object-cover rounded-lg shadow-md mb-6 md:mb-0">
                </div>
                <div>
                    <h1 class="text-3xl lg:text-4xl font-bold text-gray-800 mb-3">${productName}</h1>
                    <p class="text-md text-gray-500 mb-4 italic">${categoryName}</p>
                    <p class="text-2xl font-semibold text-indigo-600 mb-6">${product.price_eur.toFixed(2)} € ${productUnit}</p>
                    
                    <div class="prose prose-indigo max-w-none text-gray-700">
                        <h2 class="text-xl font-semibold mt-0 mb-2 text-gray-700">${getTranslatedText({titles: {fr: "Description du Produit", en: "Product Description"}}, 'titles')}</h2>
                        <p>${productDescLong}</p>
                    </div>
                    <!-- Add to cart button, etc. -->
                </div>
            </div>

            <div class="mt-10 pt-8 border-t border-gray-200">
                <h2 class="text-2xl font-semibold mb-4 text-gray-700">${getTranslatedText({titles: {fr: "Détails de la Catégorie", en: "Category Details"}}, 'titles')}</h2>
                <div class="space-y-3 text-gray-600">
                    ${categoryDesc ? `<p><strong>${getTranslatedText({fields: {fr: "Description Catégorie", en: "Category Description"}}, 'fields')}:</strong> ${categoryDesc}</p>` : ''}
                    ${categorySpecies ? `<p><strong>${getTranslatedText({fields: {fr: "Espèce/Origine", en: "Species/Origin"}}, 'fields')}:</strong> ${categorySpecies}</p>` : ''}
                    ${categoryMainIngredients ? `<p><strong>${getTranslatedText({fields: {fr: "Ingrédients Principaux", en: "Main Ingredients"}}, 'fields')}:</strong> ${categoryMainIngredients}</p>` : ''}
                    ${categoryIngredientsNotes ? `<p><strong>${getTranslatedText({fields: {fr: "Notes sur les Ingrédients", en: "Ingredient Notes"}}, 'fields')}:</strong> ${categoryIngredientsNotes}</p>` : ''}
                    ${categoryFreshPreserved ? `<p><strong>${getTranslatedText({fields: {fr: "Conservation", en: "Preservation"}}, 'fields')}:</strong> ${categoryFreshPreserved}</p>` : ''}
                    ${categorySizeDetails ? `<p><strong>${getTranslatedText({fields: {fr: "Détails Taille/Portion", en: "Size/Portion Details"}}, 'fields')}:</strong> ${categorySizeDetails}</p>` : ''}
                    ${categoryPairings ? `<p><strong>${getTranslatedText({fields: {fr: "Accords", en: "Pairings"}}, 'fields')}:</strong> ${categoryPairings}</p>` : ''}
                    ${categoryWeightInfo ? `<p><strong>${getTranslatedText({fields: {fr: "Info Poids", en: "Weight Info"}}, 'fields')}:</strong> ${categoryWeightInfo}</p>` : ''}
                    ${categoryNotes ? `<p><strong>${getTranslatedText({fields: {fr: "Notes Générales", en: "General Notes"}}, 'fields')}:</strong> ${categoryNotes}</p>` : ''}
                </div>
            </div>
        </article>
    `;
    container.appendChild(detailWrapper);
}