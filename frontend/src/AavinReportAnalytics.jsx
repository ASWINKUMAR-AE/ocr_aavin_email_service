import { useState } from 'react';
import { BarChart3, PieChart, Layers, Package, Droplets, TrendingUp, Filter, CheckCircle2 } from 'lucide-react';

export default function AavinReportAnalytics({ report }) {
  const [sortBy, setSortBy] = useState('litres'); // 'litres' | 'packets' | 'trays'
  const [filterCategory, setFilterCategory] = useState('ALL'); // 'ALL' | 'MILK' | 'CURD_BUTTERMILK'
  const [hoveredProduct, setHoveredProduct] = useState(null);

  if (!report || !report.items) return null;

  const productItems = report.items.filter(i => i.row_type === 'PRODUCT');
  const milkTotalLtr = parseFloat(report.milk_total_litres || 0);
  const curdTotalLtr = parseFloat(report.curd_buttermilk_total_litres || 0);
  const grandTotalLtr = parseFloat(report.grand_total_litres || 1);

  const milkTotalPkts = parseInt(report.milk_total_packets || 0, 10);
  const curdTotalPkts = parseInt(report.curd_buttermilk_total_packets || 0, 10);
  const grandTotalPkts = parseInt(report.grand_total_packets || 1, 10);

  const milkTotalTrays = parseFloat(report.milk_total_trays || 0);
  const curdTotalTrays = parseFloat(report.curd_buttermilk_total_trays || 0);
  const grandTotalTrays = parseFloat(report.grand_total_trays || 1);

  const milkPercent = ((milkTotalLtr / grandTotalLtr) * 100).toFixed(1);
  const curdPercent = ((curdTotalLtr / grandTotalLtr) * 100).toFixed(1);

  // Filter & sort products
  const filteredProducts = productItems.filter(p => {
    if (filterCategory === 'ALL') return true;
    return p.category === filterCategory;
  });

  const sortedProducts = [...filteredProducts].sort((a, b) => {
    if (sortBy === 'litres') return parseFloat(b.quantity_litres) - parseFloat(a.quantity_litres);
    if (sortBy === 'packets') return parseInt(b.quantity_packets, 10) - parseInt(a.quantity_packets, 10);
    return parseFloat(b.quantity_trays) - parseFloat(a.quantity_trays);
  });

  const maxVal = Math.max(
    ...sortedProducts.map(p => {
      if (sortBy === 'litres') return parseFloat(p.quantity_litres);
      if (sortBy === 'packets') return parseInt(p.quantity_packets, 10);
      return parseFloat(p.quantity_trays);
    }),
    1
  );

  // Donut chart calculations
  const radius = 60;
  const circumference = 2 * Math.PI * radius;
  const milkStrokeDash = (milkTotalLtr / grandTotalLtr) * circumference;
  const curdStrokeDash = (curdTotalLtr / grandTotalLtr) * circumference;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', marginBottom: '1.5rem' }}>
      {/* 1. Executive Summary KPI Ribbon */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '1rem'
        }}
      >
        {/* Total Litres Card */}
        <div
          style={{
            background: 'var(--card, #ffffff)',
            borderRadius: '12px',
            padding: '1.1rem 1.25rem',
            border: '1px solid var(--border, #cbd5e1)',
            boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.4rem'
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--muted, #64748b)', textTransform: 'uppercase' }}>
              Total Volume
            </span>
            <div style={{ background: '#e0f2fe', color: '#0284c7', padding: '6px', borderRadius: '8px' }}>
              <Droplets size={16} />
            </div>
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: 700, color: 'var(--text, #0f172a)' }}>
            {parseFloat(report.grand_total_litres || 0).toLocaleString('en-IN', { minimumFractionDigits: 3, maximumFractionDigits: 3 })}
            <span style={{ fontSize: '0.85rem', fontWeight: 500, color: 'var(--muted, #64748b)', marginLeft: '4px' }}>Ltr</span>
          </div>
          <div style={{ fontSize: '0.78rem', color: '#0284c7', fontWeight: 500 }}>
            Milk: {milkPercent}% &bull; Curd: {curdPercent}%
          </div>
        </div>

        {/* Total Packets Card */}
        <div
          style={{
            background: 'var(--card, #ffffff)',
            borderRadius: '12px',
            padding: '1.1rem 1.25rem',
            border: '1px solid var(--border, #cbd5e1)',
            boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.4rem'
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--muted, #64748b)', textTransform: 'uppercase' }}>
              Total Packets
            </span>
            <div style={{ background: '#f3e8ff', color: '#9333ea', padding: '6px', borderRadius: '8px' }}>
              <Package size={16} />
            </div>
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: 700, color: 'var(--text, #0f172a)' }}>
            {parseInt(report.grand_total_packets || 0, 10).toLocaleString('en-IN')}
            <span style={{ fontSize: '0.85rem', fontWeight: 500, color: 'var(--muted, #64748b)', marginLeft: '4px' }}>Pkts</span>
          </div>
          <div style={{ fontSize: '0.78rem', color: '#9333ea', fontWeight: 500 }}>
            Milk: {milkTotalPkts.toLocaleString()} &bull; Curd: {curdTotalPkts.toLocaleString()}
          </div>
        </div>

        {/* Total Trays / Crates Card */}
        <div
          style={{
            background: 'var(--card, #ffffff)',
            borderRadius: '12px',
            padding: '1.1rem 1.25rem',
            border: '1px solid var(--border, #cbd5e1)',
            boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.4rem'
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--muted, #64748b)', textTransform: 'uppercase' }}>
              Total Trays (Crates)
            </span>
            <div style={{ background: '#dcfce7', color: '#16a34a', padding: '6px', borderRadius: '8px' }}>
              <Layers size={16} />
            </div>
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: 700, color: 'var(--text, #0f172a)' }}>
            {parseFloat(report.grand_total_trays || 0).toLocaleString('en-IN', { minimumFractionDigits: 3, maximumFractionDigits: 3 })}
            <span style={{ fontSize: '0.85rem', fontWeight: 500, color: 'var(--muted, #64748b)', marginLeft: '4px' }}>Trays</span>
          </div>
          <div style={{ fontSize: '0.78rem', color: '#16a34a', fontWeight: 500 }}>
            Milk: {milkTotalTrays.toFixed(1)} &bull; Curd: {curdTotalTrays.toFixed(1)}
          </div>
        </div>

        {/* Product Count & Highest Product */}
        <div
          style={{
            background: 'var(--card, #ffffff)',
            borderRadius: '12px',
            padding: '1.1rem 1.25rem',
            border: '1px solid var(--border, #cbd5e1)',
            boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.4rem'
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--muted, #64748b)', textTransform: 'uppercase' }}>
              Leading Product
            </span>
            <div style={{ background: '#ffedd5', color: '#ea580c', padding: '6px', borderRadius: '8px' }}>
              <TrendingUp size={16} />
            </div>
          </div>
          <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text, #0f172a)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {sortedProducts[0]?.product_name || 'N/A'}
          </div>
          <div style={{ fontSize: '0.78rem', color: '#ea580c', fontWeight: 500 }}>
            {parseFloat(sortedProducts[0]?.quantity_litres || 0).toLocaleString('en-IN', { minimumFractionDigits: 1 })} Ltr ({((parseFloat(sortedProducts[0]?.quantity_litres || 0) / grandTotalLtr) * 100).toFixed(1)}% of total)
          </div>
        </div>
      </div>

      {/* 2. Visual Charts Container (2-Column Grid) */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))',
          gap: '1.25rem'
        }}
      >
        {/* Left: Product Volume Breakdown Horizontal Bar Chart */}
        <div
          style={{
            background: 'var(--card, #ffffff)',
            borderRadius: '12px',
            padding: '1.25rem',
            border: '1px solid var(--border, #cbd5e1)',
            boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
            display: 'flex',
            flexDirection: 'column',
            gap: '1rem'
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <BarChart3 size={18} style={{ color: 'var(--accent, #0284c7)' }} />
              <h3 style={{ margin: 0, fontSize: '0.98rem', fontWeight: 600 }}>
                Product Volume Distribution
              </h3>
            </div>
            {/* Sorters & Filters */}
            <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
              <div style={{ display: 'inline-flex', background: 'var(--soft, #f1f5f9)', borderRadius: '6px', padding: '2px' }}>
                <button
                  onClick={() => setSortBy('litres')}
                  style={{
                    background: sortBy === 'litres' ? 'var(--surface, #ffffff)' : 'transparent',
                    border: 'none',
                    borderRadius: '4px',
                    padding: '3px 8px',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    color: sortBy === 'litres' ? '#0284c7' : 'var(--muted, #64748b)'
                  }}
                >
                  Ltr
                </button>
                <button
                  onClick={() => setSortBy('packets')}
                  style={{
                    background: sortBy === 'packets' ? 'var(--surface, #ffffff)' : 'transparent',
                    border: 'none',
                    borderRadius: '4px',
                    padding: '3px 8px',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    color: sortBy === 'packets' ? '#0284c7' : 'var(--muted, #64748b)'
                  }}
                >
                  Packets
                </button>
                <button
                  onClick={() => setSortBy('trays')}
                  style={{
                    background: sortBy === 'trays' ? 'var(--surface, #ffffff)' : 'transparent',
                    border: 'none',
                    borderRadius: '4px',
                    padding: '3px 8px',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    color: sortBy === 'trays' ? '#0284c7' : 'var(--muted, #64748b)'
                  }}
                >
                  Trays
                </button>
              </div>

              <select
                value={filterCategory}
                onChange={e => setFilterCategory(e.target.value)}
                style={{
                  fontSize: '0.75rem',
                  padding: '3px 6px',
                  borderRadius: '6px',
                  border: '1px solid var(--border, #cbd5e1)',
                  background: 'var(--surface, #ffffff)',
                  color: 'var(--text, #1e293b)'
                }}
              >
                <option value="ALL">All Categories</option>
                <option value="MILK">Milk Only</option>
                <option value="CURD_BUTTERMILK">Curd Only</option>
              </select>
            </div>
          </div>

          {/* Bar Chart Rows */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', maxHeight: '380px', overflowY: 'auto', paddingRight: '4px' }}>
            {sortedProducts.map((p, idx) => {
              const val = sortBy === 'litres' ? parseFloat(p.quantity_litres) : sortBy === 'packets' ? parseInt(p.quantity_packets, 10) : parseFloat(p.quantity_trays);
              const pct = ((val / maxVal) * 100).toFixed(1);
              const totalShare = ((parseFloat(p.quantity_litres) / grandTotalLtr) * 100).toFixed(1);
              const isMilk = p.category === 'MILK';
              const isHovered = hoveredProduct === p.product_name;

              return (
                <div
                  key={p.item_no || p.product_name}
                  onMouseEnter={() => setHoveredProduct(p.product_name)}
                  onMouseLeave={() => setHoveredProduct(null)}
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '2px',
                    padding: '4px 6px',
                    borderRadius: '6px',
                    background: isHovered ? 'var(--soft, #f8fafc)' : 'transparent',
                    transition: 'background 0.2s'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem' }}>
                    <span style={{ fontWeight: 600, color: 'var(--text, #1e293b)' }}>
                      {idx + 1}. {p.product_name}
                    </span>
                    <span style={{ fontWeight: 600, color: isMilk ? '#0284c7' : '#16a34a' }}>
                      {sortBy === 'litres' ? `${val.toLocaleString('en-IN', { minimumFractionDigits: 3 })} Ltr` : sortBy === 'packets' ? `${val.toLocaleString()} Pkts` : `${val.toFixed(3)} Trays`}
                      <small style={{ color: 'var(--muted, #94a3b8)', marginLeft: '6px' }}>({totalShare}%)</small>
                    </span>
                  </div>
                  <div style={{ height: '8px', width: '100%', background: 'var(--soft, #f1f5f9)', borderRadius: '4px', overflow: 'hidden' }}>
                    <div
                      style={{
                        height: '100%',
                        width: `${pct}%`,
                        background: isMilk ? 'linear-gradient(90deg, #38bdf8, #0284c7)' : 'linear-gradient(90deg, #4ade80, #16a34a)',
                        borderRadius: '4px',
                        transition: 'width 0.4s ease-out'
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right: Category Split Donut Chart & Product Breakdown Card */}
        <div
          style={{
            background: 'var(--card, #ffffff)',
            borderRadius: '12px',
            padding: '1.25rem',
            border: '1px solid var(--border, #cbd5e1)',
            boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            gap: '1rem'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <PieChart size={18} style={{ color: 'var(--accent, #0284c7)' }} />
            <h3 style={{ margin: 0, fontSize: '0.98rem', fontWeight: 600 }}>
              Category Volume Ratio (Milk vs. Curd)
            </h3>
          </div>

          {/* Donut Visualizer */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '2rem', padding: '1rem 0' }}>
            <div style={{ position: 'relative', width: '150px', height: '150px' }}>
              <svg width="150" height="150" viewBox="0 0 160 160">
                {/* Background circle */}
                <circle cx="80" cy="80" r={radius} fill="none" stroke="#f1f5f9" strokeWidth="22" />
                {/* Milk Arc */}
                <circle
                  cx="80"
                  cy="80"
                  r={radius}
                  fill="none"
                  stroke="#0284c7"
                  strokeWidth="22"
                  strokeDasharray={`${milkStrokeDash} ${circumference}`}
                  strokeDashoffset="0"
                  transform="rotate(-90 80 80)"
                  style={{ transition: 'stroke-dasharray 0.5s ease' }}
                />
                {/* Curd Arc */}
                <circle
                  cx="80"
                  cy="80"
                  r={radius}
                  fill="none"
                  stroke="#16a34a"
                  strokeWidth="22"
                  strokeDasharray={`${curdStrokeDash} ${circumference}`}
                  strokeDashoffset={`-${milkStrokeDash}`}
                  transform="rotate(-90 80 80)"
                  style={{ transition: 'stroke-dasharray 0.5s ease' }}
                />
              </svg>
              <div
                style={{
                  position: 'absolute',
                  inset: 0,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  pointerEvents: 'none'
                }}
              >
                <span style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--text, #0f172a)' }}>{milkPercent}%</span>
                <span style={{ fontSize: '0.7rem', color: 'var(--muted, #64748b)', fontWeight: 600 }}>MILK SHARE</span>
              </div>
            </div>

            {/* Legend & Stats */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ width: '12px', height: '12px', borderRadius: '3px', background: '#0284c7', display: 'inline-block' }} />
                  <strong style={{ fontSize: '0.88rem' }}>Milk Products</strong>
                </div>
                <span style={{ fontSize: '0.8rem', color: 'var(--muted, #64748b)', marginLeft: '18px' }}>
                  {milkTotalLtr.toLocaleString('en-IN', { minimumFractionDigits: 3 })} Ltr ({milkPercent}%)
                </span>
                <span style={{ fontSize: '0.75rem', color: 'var(--muted, #94a3b8)', marginLeft: '18px' }}>
                  {milkTotalPkts.toLocaleString()} Packets &bull; {milkTotalTrays.toFixed(1)} Trays
                </span>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ width: '12px', height: '12px', borderRadius: '3px', background: '#16a34a', display: 'inline-block' }} />
                  <strong style={{ fontSize: '0.88rem' }}>Curd & Buttermilk</strong>
                </div>
                <span style={{ fontSize: '0.8rem', color: 'var(--muted, #64748b)', marginLeft: '18px' }}>
                  {curdTotalLtr.toLocaleString('en-IN', { minimumFractionDigits: 3 })} Ltr ({curdPercent}%)
                </span>
                <span style={{ fontSize: '0.75rem', color: 'var(--muted, #94a3b8)', marginLeft: '18px' }}>
                  {curdTotalPkts.toLocaleString()} Packets &bull; {curdTotalTrays.toFixed(1)} Trays
                </span>
              </div>
            </div>
          </div>

          {/* Quick Dispatch Insight Card */}
          <div
            style={{
              background: 'var(--soft, #f8fafc)',
              borderRadius: '8px',
              padding: '10px 14px',
              border: '1px solid var(--border, #e2e8f0)',
              fontSize: '0.82rem',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              color: 'var(--text, #334155)'
            }}
          >
            <CheckCircle2 size={16} style={{ color: '#16a34a', flexShrink: 0 }} />
            <span>
              Booking data verified for <strong>{report.shift?.toUpperCase()}</strong> shift on <strong>{report.report_date}</strong>. Ready for administrative audit and route logistics dispatch.
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
