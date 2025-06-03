// Global variables for data
let allProductsData = null;
let allCategoriesData = null;

document.addEventListener('DOMContentLoaded', async () => {
    // utils.js should have already initialized currentLang

    allProductsData = await fetchData('../data/products_details.json'); 
    allCategoriesData = await fetchData('../data/categories_details.json');

    const mainContainer = document.getElementById('nos-produits-main-container'); 

    if (!mainContainer) {
        console.error('Main container (#nos-produits-main-container) not found on nos_produits.html');
        return;
    }

    if (!allProductsData || !allCategoriesData) {
        const pError = document.createElement('p');
        pError.textContent = getTranslatedText({error: {fr: "Erreur critique: Impossible de charger les données.", en: "Critical Error: Could not load data."}}, 'error');
        mainContainer.innerHTML = ''; // Clear previous
        mainContainer.appendChild(pError);
        return;
    }

    window.addEventListener('popstate', renderPageContent);
    renderPageContent(); // Initial render
});

function renderPageContent() {
    const params = new URLSearchParams(window.location.search);
    const productId = params.get('id');
    const urlLang = params.get('lang');

    if (urlLang && ['fr', 'en'].includes(urlLang) && urlLang !== currentLang) {
        setLanguage(urlLang); 
    }

    const mainContainer = document.getElementById('nos-produits-main-container');
    if (!mainContainer) return;

    mainContainer.innerHTML = ''; // Clear previous content

    if (productId) {
        displaySingleProductDetails(productId, mainContainer);
    } else {
        displayProductList(mainContainer);
    }
}

function displayProductList(container) {
    const productListWrapper = document.createElement('div');
    productListWrapper.id = 'product-list-container'; 
    productListWrapper.className = 'grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6';

    if (Object.keys(allProductsData).length === 0) {
        const pEmpty = document.createElement('p');
        pEmpty.textContent = getTranslatedText({empty: {fr: "Aucun produit à afficher.", en: "No products to display."}}, 'empty');
        productListWrapper.appendChild(pEmpty);
        container.appendChild(productListWrapper);
        return;
    }

    for (const productId in allProductsData) {
        const product = allProductsData[productId];
        const category = allCategoriesData[product.category_id] || {};

        const productCard = document.createElement('div');
        productCard.className = 'product-card bg-white shadow-xl hover:shadow-2xl transition-shadow duration-300 rounded-lg overflow-hidden flex flex-col';

        const productName = getTranslatedText(product, 'name');
        const productDescriptionShort = getTranslatedText(product, 'description_short');
        const categoryName = getTranslatedText(category, 'name');
        const productUnit = getTranslatedText(product, 'unit');
        const detailUrl = `?id=${productId}&lang=${currentLang}`;

        const img = document.createElement('img');
        img.src = product.image_url || '../images/placeholder.png';
        img.alt = productName; // Alt text
        img.className = 'w-full h-56 object-cover';
        productCard.appendChild(img);

        const contentDiv = document.createElement('div');
        contentDiv.className = 'p-5 flex flex-col flex-grow';

        const h3 = document.createElement('h3');
        h3.className = 'text-xl font-semibold text-gray-800 mb-2';
        h3.textContent = productName; // XSS: textContent
        contentDiv.appendChild(h3);

        const pCategory = document.createElement('p');
        pCategory.className = 'text-xs text-gray-500 mb-1 italic';
        pCategory.textContent = categoryName; // XSS: textContent
        contentDiv.appendChild(pCategory);

        const pDescShort = document.createElement('p');
        pDescShort.className = 'text-gray-600 text-sm mb-3 flex-grow';
        pDescShort.textContent = productDescriptionShort; // XSS: textContent
        contentDiv.appendChild(pDescShort);
        
        const pPrice = document.createElement('p');
        pPrice.className = 'text-lg font-bold text-indigo-600 mb-4';
        pPrice.textContent = `${product.price_eur.toFixed(2)} € ${productUnit}`; // XSS: Price/unit, safe
        contentDiv.appendChild(pPrice);

        const detailLink = document.createElement('a');
        detailLink.href = detailUrl;
        detailLink.className = 'mt-auto block w-full text-center bg-indigo-500 hover:bg-indigo-700 text-white font-semibold py-2 px-4 rounded-md transition-colors duration-300';
        detailLink.textContent = getTranslatedText({details: {fr: "Voir détails", en: "View Details"}}, 'details'); // XSS: Translated string
        contentDiv.appendChild(detailLink);
        
        productCard.appendChild(contentDiv);
        productListWrapper.appendChild(productCard);
    }
    container.appendChild(productListWrapper);
}

function displaySingleProductDetails(productId, container) {
    const product = allProductsData[productId];
    if (!product) {
        const pError = document.createElement('p');
        pError.textContent = getTranslatedText({error: {fr: "Produit non trouvé.", en: "Product not found."}}, 'error');
        container.appendChild(pError);
        return;
    }
    const category = allCategoriesData[product.category_id] || {};

    const backLinkUrl = `?lang=${currentLang}`;
    const backButtonHtml = `
        <a href="${backLinkUrl}" class="inline-block bg-gray-200 hover:bg-gray-300 text-gray-700 font-semibold py-2 px-4 rounded-md mb-6 transition-colors duration-300">
            &larr; ${getTranslatedText({back: {fr: "Retour à la liste", en: "Back to list"}}, 'back')}
        </a>`;

    const detailWrapper = document.createElement('div');
    detailWrapper.id = 'product-detail-content';
    detailWrapper.innerHTML = backButtonHtml; // Button HTML is safe

    const article = document.createElement('article');
    article.className = 'bg-white p-6 md:p-8 rounded-lg shadow-xl';
    
    const gridDiv = document.createElement('div');
    gridDiv.className = 'grid grid-cols-1 md:grid-cols-2 gap-8 items-start';

    const imgDiv = document.createElement('div');
    const img = document.createElement('img');
    img.src = product.image_url || '../images/placeholder.png';
    img.alt = getTranslatedText(product, 'name'); // Alt text
    img.className = 'w-full h-auto object-cover rounded-lg shadow-md mb-6 md:mb-0';
    imgDiv.appendChild(img);
    gridDiv.appendChild(imgDiv);

    const infoDiv = document.createElement('div');
    const h1 = document.createElement('h1');
    h1.className = 'text-3xl lg:text-4xl font-bold text-gray-800 mb-3';
    h1.textContent = getTranslatedText(product, 'name'); // XSS
    infoDiv.appendChild(h1);

    const pCategory = document.createElement('p');
    pCategory.className = 'text-md text-gray-500 mb-4 italic';
    pCategory.textContent = getTranslatedText(category, 'name'); // XSS
    infoDiv.appendChild(pCategory);

    const pPrice = document.createElement('p');
    pPrice.className = 'text-2xl font-semibold text-indigo-600 mb-6';
    pPrice.textContent = `${product.price_eur.toFixed(2)} € ${getTranslatedText(product, 'unit')}`; // XSS
    infoDiv.appendChild(pPrice);

    const proseDiv = document.createElement('div');
    proseDiv.className = 'prose prose-indigo max-w-none text-gray-700';
    const h2Desc = document.createElement('h2');
    h2Desc.className = 'text-xl font-semibold mt-0 mb-2 text-gray-700';
    h2Desc.textContent = getTranslatedText({titles: {fr: "Description du Produit", en: "Product Description"}}, 'titles'); // XSS
    proseDiv.appendChild(h2Desc);
    const pDescLong = document.createElement('p');
    pDescLong.textContent = getTranslatedText(product, 'description_long'); // XSS
    proseDiv.appendChild(pDescLong);
    infoDiv.appendChild(proseDiv);
    gridDiv.appendChild(infoDiv);
    article.appendChild(gridDiv);

    const categoryDetailDiv = document.createElement('div');
    categoryDetailDiv.className = 'mt-10 pt-8 border-t border-gray-200';
    const h2CatDetail = document.createElement('h2');
    h2CatDetail.className = 'text-2xl font-semibold mb-4 text-gray-700';
    h2CatDetail.textContent = getTranslatedText({titles: {fr: "Détails de la Catégorie", en: "Category Details"}}, 'titles'); // XSS
    categoryDetailDiv.appendChild(h2CatDetail);

    const catSpaceYDiv = document.createElement('div');
    catSpaceYDiv.className = 'space-y-3 text-gray-600';
    
    // Helper to add category details safely
    function addCategoryDetail(labelKey, valueText) {
        if (valueText && valueText.trim() && valueText.trim().toLowerCase() !== 'n/a') {
            const p = document.createElement('p');
            const strong = document.createElement('strong');
            strong.textContent = getTranslatedText({fields: labelKey}, 'fields') + ": "; // XSS
            p.appendChild(strong);
            p.append(valueText); // XSS: valueText is from getTranslatedText, presumed safe or needs sanitization if HTML
            catSpaceYDiv.appendChild(p);
        }
    }
    
    addCategoryDetail('Description Catégorie', getTranslatedText(category, 'description'));
    addCategoryDetail('Espèce/Origine', getTranslatedText(category, 'species'));
    addCategoryDetail('Ingrédients Principaux', getTranslatedText(category, 'main_ingredients'));
    // ... add all other category fields similarly ...
    addCategoryDetail('Notes sur les Ingrédients', getTranslatedText(category, 'ingredients_notes'));
    addCategoryDetail('Conservation', getTranslatedText(category, 'fresh_vs_preserved'));
    addCategoryDetail('Détails Taille/Portion', getTranslatedText(category, 'size_details'));
    addCategoryDetail('Accords', getTranslatedText(category, 'pairings'));
    addCategoryDetail('Info Poids', getTranslatedText(category, 'weight_info'));
    addCategoryDetail('Notes Générales', getTranslatedText(category, 'category_notes'));

    categoryDetailDiv.appendChild(catSpaceYDiv);
    article.appendChild(categoryDetailDiv);
    detailWrapper.appendChild(article);
    container.appendChild(detailWrapper);
}
