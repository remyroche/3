const express = require('express');
const cors = require('cors');
const bcrypt = require('bcryptjs'); // Using bcryptjs for password hashing
const jwt = require('jsonwebtoken');

const app = express();
const PORT = process.env.PORT || 5001; // Changed to 5001 to avoid conflict

// Middleware
const corsOptions = {
    origin: 'http://127.0.0.1:5500', // Your frontend's origin
    // origin: function (origin, callback) {
    //     console.log('[CORS] Request received. Origin:', origin);
    //     const allowedOrigins = ['http://127.0.0.1:5500']; // Ensure this matches your frontend
    //     if (!origin || allowedOrigins.includes(origin)) {
    //         console.log('[CORS] Origin allowed.');
    //         callback(null, true);
    //     } else {
    //         console.error('[CORS] Origin NOT allowed:', origin);
    //         callback(new Error('Not allowed by CORS')); // This error will be passed to Express error handlers
    //     }
    // },
    methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'], // Allowed methods
    allowedHeaders: ['Content-Type', 'Authorization'], // Allowed headers
    optionsSuccessStatus: 200 // Some legacy browsers (IE11, various SmartTVs) choke on 204
};
app.use(cors(corsOptions)); // Enable CORS with specific options

// IMPORTANT: Ensure app.use(cors(corsOptions)) is placed before your route definitions.

app.use(express.json()); // To parse JSON request bodies
app.use(express.urlencoded({ extended: true })); // To parse URL-encoded request bodies

// --- Configuration ---
// In a real application, JWT_SECRET should be a strong, unique key stored in an environment variable.
const JWT_SECRET = process.env.JWT_SECRET || 'your-very-secure-and-long-secret-key-for-jwt-shhh'; 

// Admin credentials - In a real application, this would come from a database and password would be hashed.
const ADMIN_EMAIL = 'admin@maisontruvra.com';
const PLAIN_ADMIN_PASSWORD = 'SecureAdminP@ss1'; // For hashing on startup
let HASHED_ADMIN_PASSWORD; // Will store the hashed password

const SALT_ROUNDS = 10; // For bcrypt

// In-memory store for products (replace with a database in a real app)
let products = [
    {
        id: "truffe-noire-classique-01",
        name: "Truffe Noire Classique",
        category: "Fresh Truffles",
        short_description: "Notre truffe noire classique, un délice intemporel pour sublimer vos plats.",
        long_description: "La Tuber Melanosporum, aussi connue sous le nom de Truffe Noire du Périgord, est célèbre pour son parfum puissant et envoûtant. Elle offre des notes complexes de sous-bois, de terre humide, et parfois de chocolat ou de fruits secs. Sa chair est ferme, d'un noir violacé parcouru de fines veines blanches.",
        image_url_main: "https://images.unsplash.com/photo-1587904300987-649350119856?ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&w=600&q=80",
        image_urls_thumb: [
            "https://images.unsplash.com/photo-1587904300987-649350119856?ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&w=100&q=80",
            "https://images.unsplash.com/photo-1615361200132-ef013b456a84?ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&w=100&q=80"
        ],
        species: "Tuber Melanosporum",
        origin: "France (Provence)",
        seasonality: "De décembre à mars",
        ideal_uses: "Omelettes, pâtes, risottos, sauces, viandes blanches.",
        sensory_description: "Arômes intenses et persistants, saveur fine et complexe.",
        pairing_suggestions: "Vins rouges légers (Bourgogne), Champagne brut.",
        is_published: true,
        base_price: 55.00,
        stock_quantity: 15, // For simple products, this is the direct stock
        weight_options: []
    },
    {
        id: "truffe-blanche-prestige-02",
        name: "Truffe Blanche Prestige d'Alba",
        category: "Fresh Truffles",
        short_description: "L'arôme envoûtant de la truffe blanche, disponible en plusieurs poids pour une expérience sur mesure.",
        long_description: "La Tuber Magnatum Pico, ou Truffe Blanche d'Alba, est le diamant de la gastronomie. Son parfum est unique, puissant, avec des notes alliacées, de foin coupé, et parfois de miel. Elle se consomme exclusivement fraîche, râpée au dernier moment sur des plats simples pour en exalter la saveur.",
        image_url_main: "https://images.unsplash.com/photo-1603053531588-cd396075552a?ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&w=600&q=80",
        image_urls_thumb: [
            "https://images.unsplash.com/photo-1603053531588-cd396075552a?ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&w=100&q=80"
        ],
        species: "Tuber Magnatum Pico",
        origin: "Italie (Piémont)",
        seasonality: "D'octobre à décembre",
        ideal_uses: "Pâtes fraîches, œufs, risottos, fondues.",
        sensory_description: "Parfum intense et volatil, saveur délicate et inoubliable.",
        pairing_suggestions: "Vins blancs structurés (Barolo blanc), vins rouges légers et fruités.",
        is_published: true,
        base_price: null, // No single base price for variant product
        stock_quantity: 0, // This will be calculated from variants for the API response
        weight_options: [
            { option_id: "tb20g", weight_grams: 20, price: 120.00, stock_quantity: 5 },
            { option_id: "tb50g", weight_grams: 50, price: 280.00, stock_quantity: 3 }
        ]
    },
    {
        id: "huile-truffee-noire-03",
        name: "Huile d'Olive Vierge Extra à la Truffe Noire",
        category: "Truffle Oils",
        short_description: "Une huile d'olive de qualité supérieure infusée avec l'arôme naturel de la truffe noire.",
        image_url_main: "https://images.unsplash.com/photo-1540420773420-75ce2ff30564?ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&w=600&q=80",
        is_published: true,
        base_price: 18.50,
        stock_quantity: 50,
        weight_options: []
    }
];

app.get('/', (req, res) => {
    res.send('Maison Trüvra Backend is running!');
});

// Middleware to optionally check for admin token
const checkAdminOptional = (req, res, next) => {
    const authHeader = req.headers.authorization;
    req.isAdminUser = false; // Default to not admin
    if (authHeader && authHeader.startsWith('Bearer ')) {
        const token = authHeader.split(' ')[1];
        try {
            const decoded = jwt.verify(token, JWT_SECRET);
            if (decoded && decoded.isAdmin) { // Ensure your JWT payload for admin has isAdmin: true
                req.isAdminUser = true;
            }
        } catch (err) {
            // Token invalid or expired, proceed as non-admin
            console.log("Admin token check: Invalid or expired token.");
        }
    }
    next();
};

// Admin Login Route
app.post('/api/admin/login', async (req, res) => {
    const { email, password: plainTextPassword } = req.body;
    console.log('--- Login Attempt Received ---');
    console.log('Received Email: "' + email + '" (Length: ' + (email ? email.length : 0) + ')');
    // Avoid logging plain text password in production or sensitive logs
    // console.log('Received Password: "' + plainTextPassword + '" (Length: ' + (plainTextPassword ? plainTextPassword.length : 0) + ')');
    console.log('--- Comparing Against ---');
    console.log('Expected ADMIN_EMAIL: "' + ADMIN_EMAIL + '" (Length: ' + ADMIN_EMAIL.length + ')');

    if (!email || !plainTextPassword) {
        return res.status(400).json({ success: false, message: 'Email and password are required.' });
    }

    if (email === ADMIN_EMAIL) {
        try {
            const passwordMatch = await bcrypt.compare(plainTextPassword, HASHED_ADMIN_PASSWORD);
            if (passwordMatch) {
                console.log('Credentials MATCHED!');
                // Passwords match - Successful login
                // Generate a JWT
                const payload = { email: ADMIN_EMAIL, isAdmin: true }; // Add any other relevant user info to payload
                const token = jwt.sign(payload, JWT_SECRET, { expiresIn: '1h' }); // Token expires in 1 hour

                console.log('Login successful for:', email);
                return res.json({ success: true, message: 'Login successful!', token: token });
            } else {
                console.log('Password DID NOT MATCH.');
                console.log('Login failed (password mismatch) for:', email);
                return res.status(401).json({ success: false, message: 'Invalid email or password.' });
            }
        } catch (error) {
            console.error("Error during password comparison:", error);
            return res.status(500).json({ success: false, message: 'Server error during login.' });
        }
    } else {
        console.log('Email DID NOT MATCH.');
        console.log('Login failed (email mismatch) for:', email);
        return res.status(401).json({ success: false, message: 'Invalid email or password.' });
    }
});

// --- Products API Endpoints ---

// GET all products
app.get('/api/products', checkAdminOptional, (req, res) => {
    console.log(`GET /api/products request received. isAdmin: ${req.isAdminUser}`);
    
    let productsToProcess = products;
    // If it's NOT an admin user making the request, filter for published products. Admins see all.
    if (!req.isAdminUser) {
        productsToProcess = products.filter(p => p.is_published === true);
    }
    
    const processedProducts = productsToProcess.map(p => {
        const product = { ...p }; // Shallow copy
        if (product.weight_options && product.weight_options.length > 0) {
            let minPrice = Infinity;
            let totalVariantStock = 0;
            let hasAvailableVariant = false;

            product.weight_options.forEach(opt => {
                if (opt.stock_quantity > 0) {
                    minPrice = Math.min(minPrice, opt.price);
                    hasAvailableVariant = true;
                }
                totalVariantStock += opt.stock_quantity;
            });
            
            product.starting_price = hasAvailableVariant ? minPrice : null;
            product.stock_quantity = totalVariantStock; 
            // product.base_price is already null or should be for variant products
        } else {
            product.starting_price = product.base_price;
            // product.stock_quantity is already set for simple products
        }
        return product;
    });
    res.json({ success: true, products: processedProducts });
});

// GET a single product by ID
app.get('/api/products/:id', checkAdminOptional, (req, res) => {
    const productId = req.params.id;
    console.log(`GET /api/products/${productId} request received. isAdmin: ${req.isAdminUser}`);
    const product = products.find(p => p.id === productId);

    if (product) {
        // If not an admin user making the request, and the product is not published, return 404
        if (!req.isAdminUser && !product.is_published) {
            return res.status(404).json({ success: false, message: 'Produit non trouvé ou non publié.' });
        }

        // Process the single product (similar to the list, if needed for consistency, e.g. starting_price)
        const processedProduct = { ...product };
        if (processedProduct.weight_options && processedProduct.weight_options.length > 0) {
            let minPrice = Infinity;
            let hasAvailableVariant = false;
            processedProduct.weight_options.forEach(opt => {
                if (opt.stock_quantity > 0) {
                    minPrice = Math.min(minPrice, opt.price);
                    hasAvailableVariant = true;
                }
            });
            processedProduct.starting_price = hasAvailableVariant ? minPrice : null;
        } else {
            processedProduct.starting_price = processedProduct.base_price;
        }
        res.json(processedProduct);
    } else {
        res.status(404).json({ success: false, message: 'Produit non trouvé.' });
    }
});

// POST a new product (typically from the admin panel)
app.post('/api/products', (req, res) => {
    console.log('POST /api/products request received with body:', req.body);
    const newProduct = req.body;

    // Basic validation (extend as needed)
    if (!newProduct.id || !newProduct.name || newProduct.base_price === undefined || newProduct.initial_stock_quantity === undefined) {
        return res.status(400).json({ 
            success: false, 
            message: 'Product ID, name, base_price, and initial_stock_quantity are required.' 
        });
    }

    // Check if product ID already exists
    if (products.some(p => p.id === newProduct.id)) {
        return res.status(409).json({ success: false, message: `Product with ID ${newProduct.id} already exists.`});
    }

    // Add to our in-memory store
    products.push(newProduct);
    console.log('Product added:', newProduct);

    // In a real app, you might also generate assets here if needed
    // For now, just confirm creation
    res.status(201).json({ 
        success: true, 
        message: 'Product added successfully!', 
        product: newProduct 
    });
});

// PUT (update) an existing product
app.put('/api/products/:id', (req, res) => {
    const productId = req.params.id;
    const updatedProductData = req.body;
    console.log(`PUT /api/products/${productId} request received with body:`, updatedProductData);

    const productIndex = products.findIndex(p => p.id === productId);

    if (productIndex === -1) {
        return res.status(404).json({ success: false, message: 'Product not found.' });
    }

    // Basic validation (extend as needed)
    if (!updatedProductData.name) { // Add more checks as necessary
        return res.status(400).json({ success: false, message: 'Product name is required.' });
    }

    // Update the product (preserving its original ID from the URL param, not body)
    // Ensure all fields are correctly updated, especially nested ones like weight_options
    products[productIndex] = { ...products[productIndex], ...updatedProductData, id: productId };
    
    console.log('Product updated:', products[productIndex]);
    res.json({ 
        success: true, 
        message: 'Product updated successfully!', 
        product: products[productIndex] // Return the updated product
    });
});
// --- Admin Inventory Endpoint ---
app.get('/admin/inventory', (req, res) => {
    // In a real application, you'd fetch this from a database,
    // including individual stock items with UIDs, production/expiration dates.
    // For now, we'll adapt the existing products data.

    console.log('GET /admin/inventory request received');

    const inventoryData = products.map(p => {
        let items = [];
        if (p.weight_options && p.weight_options.length > 0) {
            items = p.weight_options.map((opt, index) => ({
                item_uid: `${p.id}_variant_${opt.option_id || index}`, // Create a dummy UID
                production_date: new Date(Date.now() - Math.random() * 30 * 24 * 60 * 60 * 1000).toISOString(), // Dummy past date
                expiration_date: new Date(Date.now() + Math.random() * 365 * 24 * 60 * 60 * 1000).toISOString(), // Dummy future date
                stock_quantity: opt.stock_quantity, // Use variant stock
                weight_grams: opt.weight_grams
            }));
        } else if (p.stock_quantity > 0) { // For simple products
            // Create dummy individual items based on total stock for demonstration
            for (let i = 0; i < p.stock_quantity; i++) {
                items.push({
                    item_uid: `${p.id}_item_${i + 1}`,
                    production_date: new Date(Date.now() - Math.random() * 30 * 24 * 60 * 60 * 1000).toISOString(),
                    expiration_date: new Date(Date.now() + Math.random() * 365 * 24 * 60 * 60 * 1000).toISOString(),
                });
            }
        }
        return {
            product_id: p.id,
            product_name: p.name,
            items: items, // This is the list of individual items with UID, prod/exp dates
            // total_stock_available: p.stock_quantity // This would be the sum of items' stock
        };
    });

    res.json({ success: true, data: inventoryData });
});

// Placeholder for GET /api/inventory/product/:id
app.get('/api/inventory/product/:id', (req, res) => {
    const productId = req.params.id;
    console.log(`GET /api/inventory/product/${productId} request received`);
    const product = products.find(p => p.id === productId);
    if (!product) {
        return res.status(404).json({ success: false, message: 'Product not found for inventory details.' });
    }
    // Simulate detailed inventory structure
    const inventoryDetails = {
        product_id: product.id,
        product_name: product.name,
        current_stock_by_variant: product.weight_options && product.weight_options.length > 0 ? 
            product.weight_options.map(opt => ({
                option_id: opt.option_id,
                weight_grams: opt.weight_grams,
                stock_quantity: opt.stock_quantity,
                price: opt.price
            })) : [],
        current_stock: product.stock_quantity, // For simple products
        additions_log: [
            // { movement_date: new Date().toISOString(), quantity_change: 5, movement_type: 'initial_stock', notes: 'Initial stock entry', variant_option_id: product.weight_options[0]?.option_id }
        ],
        subtractions_log: []
    };
    res.json(inventoryDetails);
});

// Placeholder for POST /api/inventory/adjust
app.post('/api/inventory/adjust', (req, res) => {
    const { product_id, variant_option_id, quantity_change, movement_type, notes } = req.body;
    console.log('POST /api/inventory/adjust request received:', req.body);

    const productIndex = products.findIndex(p => p.id === product_id);
    if (productIndex === -1) {
        return res.status(404).json({ success: false, message: 'Product not found for stock adjustment.' });
    }

    if (variant_option_id) {
        const variantIndex = products[productIndex].weight_options.findIndex(opt => opt.option_id === variant_option_id);
        if (variantIndex === -1) {
            return res.status(404).json({ success: false, message: 'Product variant not found.' });
        }
        products[productIndex].weight_options[variantIndex].stock_quantity += quantity_change;
    } else {
        products[productIndex].stock_quantity += quantity_change;
    }

    // In a real app, log this movement to a database table.
    console.log(`Stock for product ${product_id} (variant: ${variant_option_id || 'N/A'}) adjusted by ${quantity_change}. Type: ${movement_type}. Notes: ${notes}`);
    res.json({ success: true, message: 'Stock adjusted successfully.' });
});

// --- Placeholder User Endpoints ---
app.get('/api/users', (req, res) => {
    console.log('GET /api/users request received');
    // Simulate user data
    const users = [
        { id: 1, email: ADMIN_EMAIL, nom: 'Admin', prenom: 'Super', is_admin: true, created_at: new Date().toISOString(), orders: [] },
        { id: 2, email: 'customer@example.com', nom: 'Client', prenom: 'Test', is_admin: false, created_at: new Date().toISOString(), orders: [] }
    ];
    res.json(users);
});

app.get('/api/users/:id', (req, res) => {
    const userId = parseInt(req.params.id);
    console.log(`GET /api/users/${userId} request received`);
    // Simulate finding a user
    const user = userId === 1 ? 
        { id: 1, email: ADMIN_EMAIL, nom: 'Admin', prenom: 'Super', is_admin: true, created_at: new Date().toISOString(), orders: [] } :
        { id: 2, email: 'customer@example.com', nom: 'Client', prenom: 'Test', is_admin: false, created_at: new Date().toISOString(), orders: [] };
    if (user && user.id === userId) return res.json(user);
    res.status(404).json({ success: false, message: 'User not found.' });
});

// --- Placeholder Order Endpoints ---
app.get('/api/orders', (req, res) => {
    console.log('GET /api/orders request received with query:', req.query);
    // Simulate order data
    const orders = [
        { order_id: 'ORD001', customer_email: 'customer@example.com', customer_name: 'Test Client', order_date: new Date().toISOString(), total_amount: 150.00, status: 'Processing', items: [], notes: [] }
    ];
    res.json(orders);
});

app.get('/api/orders/:id', (req, res) => {
    const orderId = req.params.id;
    console.log(`GET /api/orders/${orderId} request received`);
    // Simulate finding an order
    if (orderId === 'ORD001') return res.json({ order_id: 'ORD001', customer_email: 'customer@example.com', customer_name: 'Test Client', order_date: new Date().toISOString(), total_amount: 150.00, status: 'Processing', shipping_address: '123 Main St\nAnytown, USA', items: [{product_name: "Truffe Noire", variant: "20g", quantity: 1, price_at_purchase: 55.00}], notes: [{created_at: new Date().toISOString(), admin_user: "Admin", content: "Order placed."}] });
    res.status(404).json({ success: false, message: 'Order not found.' });
});

app.put('/api/orders/:id/status', (req, res) => res.json({ success: true, message: `Status for order ${req.params.id} updated (simulated).` }));
app.post('/api/orders/:id/notes', (req, res) => res.json({ success: true, message: `Note added to order ${req.params.id} (simulated).` }));


async function startServer() {
    HASHED_ADMIN_PASSWORD = await bcrypt.hash(PLAIN_ADMIN_PASSWORD, SALT_ROUNDS);
    console.log('Admin password hashed for runtime comparison.');
    app.listen(PORT, () => {
        console.log(`Server is running on http://localhost:${PORT}`);
    });
}

startServer().catch(err => console.error("Failed to start server:", err));