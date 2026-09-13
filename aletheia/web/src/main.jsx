import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import { StarTransitionProvider } from './components/StarTransition.jsx';
import './style.css';
import './constellation.css';

createRoot(document.getElementById('root')).render(<React.StrictMode><StarTransitionProvider><App /></StarTransitionProvider></React.StrictMode>);
