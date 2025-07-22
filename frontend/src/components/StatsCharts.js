import React from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8', '#82CA9D'];

function StatsCharts({ stats }) {
  // Préparation des données pour les graphiques
  const groupesData = Object.entries(stats.groupes).map(([groupe, count]) => ({
    name: `Groupe ${groupe}`,
    value: count
  }));

  const matieresData = Object.entries(stats.matieres).map(([matiere, count]) => ({
    name: matiere,
    value: count
  }));

  const profsData = Object.entries(stats.profs).map(([prof, count]) => ({
    name: prof,
    value: count
  }));

  // Données de charge hebdomadaire (moyenne par groupe)
  const chargeData = Object.entries(stats.charge_hebdo).map(([groupe, charges]) => ({
    name: `Groupe ${groupe}`,
    moyenne: (charges.reduce((a, b) => a + b, 0) / charges.length).toFixed(1),
    min: Math.min(...charges),
    max: Math.max(...charges)
  }));

  return (
    <div className="stats-container">
      {/* Statistiques globales */}
      <div className="global-stats">
        <div className="stat-card">
          <h4>Créneaux utilisés</h4>
          <p>{stats.globales.creneaux_utilises} / {stats.globales.total_creneaux}</p>
          <p className="percentage">{stats.globales.taux_utilisation}%</p>
        </div>
      </div>

      {/* Graphiques */}
      <div className="charts-grid">
        <div className="chart-container">
          <h4>Colles par groupe</h4>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={groupesData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" angle={-45} textAnchor="end" height={80} />
              <YAxis />
              <Tooltip />
              <Bar dataKey="value" fill="#8884d8" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-container">
          <h4>Colles par matière</h4>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={matieresData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({name, value}) => `${name}: ${value}`}
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
              >
                {matieresData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-container">
          <h4>Colles par professeur</h4>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={profsData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" angle={-45} textAnchor="end" height={100} />
              <YAxis />
              <Tooltip />
              <Bar dataKey="value" fill="#82ca9d" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-container">
          <h4>Charge hebdomadaire moyenne par groupe</h4>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={chargeData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" angle={-45} textAnchor="end" height={80} />
              <YAxis />
              <Tooltip />
              <Bar dataKey="moyenne" fill="#ffc658" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

export default StatsCharts;
