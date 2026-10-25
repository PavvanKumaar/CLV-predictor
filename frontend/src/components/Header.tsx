// src/components/Header.tsx
import React from 'react';
import { User } from 'lucide-react';

const Header: React.FC = () => {
  return (
    <header className="flex items-center justify-between bg-white border-b border-gray-200 px-4 py-2 shadow-sm">
      <h1 className="text-2xl font-semibold text-gray-800">CLV Prediction Dashboard</h1>
      <div className="flex items-center gap-2">
        <span className="text-gray-600">User</span>
        <User size={24} className="text-gray-600" />
      </div>
    </header>
  );
};

export default Header;
