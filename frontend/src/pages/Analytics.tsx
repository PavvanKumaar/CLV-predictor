// src/pages/Analytics.tsx
import React, { useState } from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, PieChart, Pie, Cell, BarChart, Bar, Legend } from 'recharts';
import { revenueTrend, segmentDistribution, purchaseFrequency, clvDistribution } from '../data/analytics';

// Helper components for cards
const Card: React.FC<{ title: string; value: string; subtitle?: string }> = ({ title, value, subtitle }) => (
  <div className="rounded-lg bg-white p-4 shadow-sm hover:shadow-md transition-shadow">
    <h3 className="text-sm font-medium text-gray-500">{title}</h3>
    <p className="text-2xl font-bold text-gray-800 mt-1">{value}</p>
    {subtitle && <p className="text-xs text-gray-400 mt-0.5">{subtitle}</p>}
  </div>
);

const Analytics: React.FC = () => {
  // Filters state
  const [dateRange, setDateRange] = useState('6m'); // '6m', '1y', 'all'
  const [segmentFilter, setSegmentFilter] = useState<'All' | 'High' | 'Medium' | 'Low'>('All');

  // Filtered data helpers (demo – filter only segment where applicable)
  const filteredSegmentDist = segmentFilter === 'All' ? segmentDistribution : segmentDistribution.filter(d => d.segment === segmentFilter);
  const filteredClvDist = segmentFilter === 'All' ? clvDistribution : clvDistribution.filter(d => d.segment === segmentFilter);

  // Sample summary metrics – derived from data
  const totalCustomers = segmentDistribution.reduce((sum, s) => sum + s.count, 0);
  const avgClv = clvDistribution.reduce((sum, d) => sum + d.avgClv, 0) / clvDistribution.length;
  const repeatCustomerPct = Math.round((segmentDistribution.find(s => s.segment === 'High')?.count ?? 0) / totalCustomers * 100);
  const avgOrderValue = revenueTrend.reduce((sum, r) => sum + r.revenue, 0) / revenueTrend.length;

  // Colors for pie chart
  const pieColors = ['#1E40AF', '#3B82F6', '#93C5FD']; // dark, medium, light blue

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Customer Analytics</h1>
          <p className="text-gray-600">Understand customer value, purchasing behaviour, and revenue distribution.</p>
        </div>
        <span className="inline-flex items-center rounded-full bg-yellow-100 px-3 py-1 text-sm font-medium text-yellow-800">
          SAMPLE DATA
        </span>
      </div>

      {/* Filters */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Date range</label>
          <select
            value={dateRange}
            onChange={e => setDateRange(e.target.value)}
            className="w-full rounded border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
          >
            <option value="6m">Last 6 months</option>
            <option value="1y">Last year</option>
            <option value="all">All time</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Customer segment</label>
          <select
            value={segmentFilter}
            onChange={e => setSegmentFilter(e.target.value as any)}
            className="w-full rounded border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
          >
            <option value="All">All</option>
            <option value="High">High</option>
            <option value="Medium">Medium</option>
            <option value="Low">Low</option>
          </select>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card title="Total customers analysed" value={totalCustomers.toString()} />
        <Card title="Average customer LTV" value={`$${avgClv.toFixed(0)}`} />
        <Card title="Repeat customer %" value={`${repeatCustomerPct}%`} />
        <Card title="Average order value" value={`$${avgOrderValue.toFixed(0)}`} />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Revenue Trend */}
        <div className="rounded-lg bg-white p-4 shadow-sm">
          <h3 className="text-lg font-medium mb-2">Revenue trend over time</h3>
          <LineChart width={500} height={300} data={revenueTrend} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" />
            <YAxis />
            <Tooltip />
            <Line type="monotone" dataKey="revenue" stroke="#1E40AF" strokeWidth={2} />
          </LineChart>
        </div>

        {/* Segment Distribution */}
        <div className="rounded-lg bg-white p-4 shadow-sm">
          <h3 className="text-lg font-medium mb-2">Customer segment distribution</h3>
          <PieChart width={400} height={300}>
            <Pie data={filteredSegmentDist} dataKey="count" nameKey="segment" cx="50%" cy="50%" outerRadius={80} label>
              {filteredSegmentDist.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={pieColors[index % pieColors.length]} />
              ))}
            </Pie>
            <Tooltip />
          </PieChart>
        </div>

        {/* Purchase Frequency */}
        <div className="rounded-lg bg-white p-4 shadow-sm">
          <h3 className="text-lg font-medium mb-2">Purchase frequency distribution</h3>
          <BarChart width={500} height={300} data={purchaseFrequency} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="bucket" />
            <YAxis />
            <Tooltip />
            <Bar dataKey="count" fill="#3B82F6" />
          </BarChart>
        </div>

        {/* CLV Distribution */}
        <div className="rounded-lg bg-white p-4 shadow-sm">
          <h3 className="text-lg font-medium mb-2">CLV distribution by segment</h3>
          <BarChart width={500} height={300} data={filteredClvDist} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="segment" />
            <YAxis />
            <Tooltip />
            <Bar dataKey="avgClv" fill="#1E40AF" />
          </BarChart>
        </div>
      </div>
    </div>
  );
};

export default Analytics;
