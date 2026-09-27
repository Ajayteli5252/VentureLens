import { useState } from 'react';
import Header from './components/Header';
import VentureLens from './pages/VentureLens';
import './index.css';

export default function App() {
  return (
    <>
      <Header />
      <VentureLens />
    </>
  );
}
