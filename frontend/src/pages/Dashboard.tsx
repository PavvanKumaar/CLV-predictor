// src/pages/Dashboard.tsx
import React from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

const sampleStats = {
  totalCustomers: 1200,
  totalRevenue: 350000,
  avgPredictedCLV: 280,
};

const segmentData = [
  { name: 'High', customers: 300, revenue: 120000 },
  { name: 'Medium', customers: 500, revenue: 150000 },
  { name: 'Low', customers: 400, revenue: 80000 },
];

const recentCustomers = [
  { id: 'C001', clv: 450, segment: 'High' },
  { id: 'C002', clv: 320, segment: 'Medium' },
  { id: 'C003', clv: 210, segment: 'Low' },
];

const Dashboard: React.FC = () => {
  return (
    <div className="space-y-6">
      {/* Stats cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-500">Total Customers</div>
          <div className="text-2xl font-semibold text-gray-800">{sampleStats.totalCustomers}</div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-500">Total Revenue</div>
          <div className="text-2xl font-semibold text-gray-800">${sampleStats.totalRevenue.toLocaleString()}</div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-500">Avg Predicted CLV</div>
          <div className="text-2xl font-semibold text-gray-800">${sampleStats.avgPredictedCLV}</div>
        </div>
      </div>

      {/* Segment Overview */}
      <div className="bg-white rounded-lg shadow p-4">
        <h2 className="text-lg font-medium mb-2">Customer Segment Overview</h2>
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={segmentData} margin={{ top: 20, right: 30, left: 0, bottom: 5 }}>
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip />
            <Bar dataKey="customers" fill="#17685e" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Revenue Trend (sample line chart placeholder) */}
      <div className="bg-white rounded-lg shadow p-4">
        <h2 className="text-lg font-medium mb-2">Revenue Trend (sample)</h2>
        <div className="h-48 flex items-center justify-center text-gray-500">[Line chart placeholder]</div>
      </div>

      {/* Recent Customers Table */}
      <div className="bg-white rounded-lg shadow p-4 overflow-auto">
        <h2 className="text-lg font-medium mb-2">Recent Customers</h2>
        <table className="w-full text-left">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2">Customer ID</th>
              <th className="px-4 py-2">Predicted CLV</th>
              <th className="px-4 py-2">Segment</th>
            </tr>
          </thead>
          <tbody>
            {recentCustomers.map(c => (
              <tr key={c.id} className="border-t">
                <td className="px-4 py-2">{c.id}</td>
                <td className="px-4 py-2">${c.clv}</td>
                <td className="px-4 py-2">{c.segment}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default Dashboard;
