// src/pages/Customers.tsx
import React, { useState, useMemo } from 'react';
import { Search, X, Eye } from 'lucide-react';
import { customers, type Customer } from '../data/customers';

// Helper to format currency consistently
const fmt = (n: number) => `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const SummaryCard: React.FC<{ label: string; value: React.ReactNode }> = ({ label, value }) => (
  <div className="bg-white rounded-lg shadow p-4">
    <div className="text-sm text-gray-500">{label}</div>
    <div className="text-2xl font-semibold text-gray-800">{value}</div>
  </div>
);

const Customers: React.FC = () => {
  const [search, setSearch] = useState('');
  const [segment, setSegment] = useState<'All' | 'High' | 'Medium' | 'Low'>('All');
  const [page, setPage] = useState(1);
  const itemsPerPage = 5;

  const filtered: Customer[] = useMemo(() => {
    const term = search.trim().toLowerCase();
    return customers.filter(c => {
      const matchesId = term ? c.id.toLowerCase().includes(term) : true;
      const matchesSeg = segment === 'All' ? true : c.segment === segment;
      return matchesId && matchesSeg;
    });
  }, [search, segment]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / itemsPerPage));
  const paginated = useMemo(() => {
    const start = (page - 1) * itemsPerPage;
    return filtered.slice(start, start + itemsPerPage);
  }, [filtered, page]);

  const totalCustomers = customers.length;
  const highValueCustomers = customers.filter(c => c.segment === 'High').length;
  const avgClv = customers.reduce((s, c) => s + c.predictedClv, 0) / totalCustomers;

  const clearFilters = () => {
    setSearch('');
    setSegment('All');
    setPage(1);
  };

  const goPrev = () => setPage(p => Math.max(p - 1, 1));
  const goNext = () => setPage(p => Math.min(p + 1, totalPages));

  return (
    <div className="space-y-6">
      {/* Header */}
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold text-gray-800">Customers</h1>
        <p className="text-gray-600">Explore customer value and purchasing behaviour.</p>
        <p className="text-sm text-gray-500">Sample customers shown: {filtered.length} of {totalCustomers}</p>
      </header>

      {/* Summary cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <SummaryCard label="Total customers" value={totalCustomers} />
        <SummaryCard label="High‑value customers" value={highValueCustomers} />
        <SummaryCard label="Avg. predicted CLV" value={fmt(avgClv)} />
      </div>

      {/* Controls */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div className="flex items-center border rounded bg-white overflow-hidden">
          <Search className="w-5 h-5 text-gray-400 mx-2" />
          <input
            type="text"
            placeholder="Search by ID..."
            className="px-2 py-1 focus:outline-none"
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1); }}
          />
        </div>
        <select
          value={segment}
          onChange={e => { setSegment(e.target.value as any); setPage(1); }}
          className="border rounded bg-white px-2 py-1"
        >
          <option value="All">All segments</option>
          <option value="High">High Value</option>
          <option value="Medium">Medium Value</option>
          <option value="Low">Low Value</option>
        </select>
        <button
          onClick={clearFilters}
          className="flex items-center gap-1 text-sm text-gray-600 hover:text-gray-800"
        >
          <X className="w-4 h-4" /> Clear filters
        </button>
      </div>

      {/* Table */}
      <div className="overflow-auto bg-white rounded-lg shadow">
        {paginated.length === 0 ? (
          <div className="p-8 text-center text-gray-500">No customers match the current criteria.</div>
        ) : (
          <table className="w-full table-auto">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left text-sm font-medium text-gray-600">Customer ID</th>
                <th className="px-4 py-2 text-left text-sm font-medium text-gray-600">Segment</th>
                <th className="px-4 py-2 text-left text-sm font-medium text-gray-600">Purchases</th>
                <th className="px-4 py-2 text-left text-sm font-medium text-gray-600">Historical Revenue</th>
                <th className="px-4 py-2 text-left text-sm font-medium text-gray-600">Predicted CLV</th>
                <th className="px-4 py-2 text-center text-sm font-medium text-gray-600">Action</th>
              </tr>
            </thead>
            <tbody>
              {paginated.map(c => (
                <tr key={c.id} className="border-t">
                  <td className="px-4 py-2">{c.id}</td>
                  <td className="px-4 py-2">{c.segment}</td>
                  <td className="px-4 py-2">{c.purchaseCount}</td>
                  <td className="px-4 py-2">{fmt(c.revenue)}</td>
                  <td className="px-4 py-2">{fmt(c.predictedClv)}</td>
                  <td className="px-4 py-2 text-center">
                    <button className="text-indigo-600 hover:underline flex items-center justify-center gap-1">
                      <Eye size={16} /> View
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-4 mt-4">
          <button
            onClick={goPrev}
            disabled={page === 1}
            className="px-3 py-1 bg-gray-200 rounded disabled:opacity-50"
          >
            Previous
          </button>
          <span className="text-sm text-gray-700">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={goNext}
            disabled={page === totalPages}
            className="px-3 py-1 bg-gray-200 rounded disabled:opacity-50"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
};

export default Customers;
