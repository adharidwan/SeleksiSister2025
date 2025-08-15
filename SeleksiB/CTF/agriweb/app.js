import express from 'express';
import path from 'path';
import { fileURLToPath } from 'url';
import { dirname } from 'path';
import cookieParser from 'cookie-parser';
import { registerUser, loginUser } from './routes/auth.js';
import { updateProfile, updateSettings, getUser } from './routes/profile.js';
import { verifyToken, getTokenFromCookie, setTokenCookie, clearTokenCookie } from './utils/jwt.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const app = express();

// Middleware
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(cookieParser());

// Static files
app.use('/challenge/css', express.static(path.join(__dirname, './static/css')));
app.use('/challenge/js', express.static(path.join(__dirname, './static/js')));

// Authentication middleware
const authenticate = (req, res, next) => {
    const token = req.cookies.auth_token;

    if (!token) {
        if (req.path.startsWith('/challenge/api/')) {
            return res.status(401).json({ success: false, error: 'Not authenticated' });
        }
        return res.sendFile(path.join(__dirname, './templates/login.html'));
    }

    try {
        req.user = verifyToken(token);
        next();
    } catch (error) {
        res.clearCookie('auth_token');
        if (req.path.startsWith('/challenge/api/')) {
            return res.status(401).json({ success: false, error: 'Invalid token' });
        }
        return res.sendFile(path.join(__dirname, './templates/login.html'));
    }
};

// Admin middleware - FIXED: Prevent prototype pollution with explicit checks
const isAdmin = (req, res, next) => {
    try {
        // Multiple layers of protection against prototype pollution
        const userIsAdmin = Object.prototype.hasOwnProperty.call(req.user, 'isAdmin') && req.user.isAdmin === true;
        
        if (!userIsAdmin) {
            if (req.path.startsWith('/challenge/api/')) {
                return res.status(403).json({ success: false, error: 'Not authorized' });
            }
            return res.sendFile(path.join(__dirname, './templates/unauthorized.html'));
        }
        next();
    } catch (error) {
        return res.sendFile(path.join(__dirname, './templates/unauthorized.html'));
    }
};

// Routes
app.get('/challenge', authenticate, (req, res) => {
    res.sendFile(path.join(__dirname, './templates/index.html'));
});

app.get('/challenge/admin', authenticate, isAdmin, (req, res) => {
    res.sendFile(path.join(__dirname, './templates/admin.html'));
});

app.post('/challenge/api/register', async (req, res) => {
    try {
        const { username, email, password } = req.body;
        const { user, token } = await registerUser(username, email, password);

        setTokenCookie(res, token);
        
        res.json({ 
            success: true, 
            message: 'Registration successful',
            user
        });
    } catch (error) {
        res.status(400).json({ success: false, error: error.message });
    }
});

app.post('/challenge/api/login', async (req, res) => {
    try {
        const { username, password } = req.body;
        const { user, token } = await loginUser(username, password);

        setTokenCookie(res, token);

        res.json({ 
            success: true, 
            message: 'Login successful',
            user
        });
    } catch (error) {
        res.status(400).json({ success: false, error: error.message });
    }
});

app.post('/challenge/api/logout', (req, res) => {
    clearTokenCookie(res);
    res.json({ success: true, message: 'Logged out successfully' });
});

app.post('/challenge/api/profile', authenticate, async (req, res) => {
    try {
        //  sanitization 
        const sanitizeObject = (obj) => {
            if (obj === null || typeof obj !== 'object') {
                return obj;
            }
            
            const sanitized = {};
            for (const [key, value] of Object.entries(obj)) {
                if (['__proto__', 'constructor', 'prototype', '__defineGetter__', '__defineSetter__', '__lookupGetter__', '__lookupSetter__'].includes(key)) {
                    continue;
                }
                
                if (typeof value === 'object' && value !== null) {
                    sanitized[key] = sanitizeObject(value);
                } else {
                    sanitized[key] = value;
                }
            }
            return sanitized;
        };
        
        const sanitizedData = sanitizeObject(req.body);
        const updatedProfile = await updateProfile(req.user.id, sanitizedData);
        res.json({ 
            success: true, 
            message: 'Profile updated successfully',
            profile: updatedProfile
        });
    } catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});

app.get('/challenge/api/user', authenticate, async (req, res) => {
    try {
        const user = await getUser(req.user.id);
        res.json({ success: true, user: user });
    } catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});

app.post('/challenge/api/settings', authenticate, async (req, res) => {
    try {
        const sanitizeObject = (obj) => {
            if (obj === null || typeof obj !== 'object') {
                return obj;
            }
            
            const sanitized = {};
            for (const [key, value] of Object.entries(obj)) {
                if (['__proto__', 'constructor', 'prototype', '__defineGetter__', '__defineSetter__', '__lookupGetter__', '__lookupSetter__'].includes(key)) {
                    continue;
                }
                
                if (typeof value === 'object' && value !== null) {
                    sanitized[key] = sanitizeObject(value);
                } else {
                    sanitized[key] = value;
                }
            }
            return sanitized;
        };
        
        const sanitizedData = sanitizeObject(req.body);
        const updatedSettings = await updateSettings(req.user.id, sanitizedData);
        res.json({ 
            success: true, 
            message: 'Settings updated successfully',
            settings: updatedSettings
        });
    } catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});

const PORT = process.env.PORT || 8000;
app.listen(PORT, () => {
    console.log(`Server is running on port ${PORT}`);
});