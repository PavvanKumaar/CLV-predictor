// src/components/Sidebar.tsx
import React from 'react';
import { NavLink } from 'react-router-dom';
import { Home, Users, BarChart2, Activity, Settings } from 'lucide-react';

const navItems = [
  { to: '/', label: 'Dashboard', icon: <Home size={20} /> },
  { to: '/customers', label: 'Customers', icon: <Users size={20} /> },
  { to: '/clv-prediction', label: 'CLV Prediction', icon: <BarChart2 size={20} /> },
  { to: '/analytics', label: 'Analytics', icon: <Activity size={20} /> },
  { to: '/model-performance', label: 'Model Performance', icon: <Settings size={20} /> },
];

const Sidebar: React.FC = () => {
  return (
    <aside className="w-64 bg-[#1a2b4c] text-white flex flex-col p-4">
      <div className="text-xl font-bold mb-6">CLV Predictor</div>
      <nav className="flex-1 space-y-2">
        {navItems.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            end
            className={({ isActive }) =>
              `flex items-center gap-3 py-2 px-3 rounded transition-colors ${
                isActive ? 'bg-[#334d71]' : 'hover:bg-[#334d71]'
              }`
            }
          >
            {item.icon}
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>
    </aside>
  );
};

export default Sidebar;
