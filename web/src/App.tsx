import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "@/components/Layout";
import { PanoramaPage } from "@/pages/Panorama";
import { DepartamentoPage } from "@/pages/Departamento";
import { CasosPrioritariosPage } from "@/pages/CasosPrioritarios";
import { ContratosRecientesPage } from "@/pages/ContratosRecientes";
import { CasoDetallePage } from "@/pages/CasoDetalle";
import { MetodologiaPage } from "@/pages/Metodologia";

export default function App() {
  return (
    <BrowserRouter basename={import.meta.env.BASE_URL}>
      <Layout>
        <Routes>
          <Route path="/" element={<PanoramaPage />} />
          <Route path="/departamentos/:cod" element={<DepartamentoPage />} />
          <Route path="/casos" element={<CasosPrioritariosPage />} />
          <Route path="/recientes" element={<ContratosRecientesPage />} />
          <Route path="/casos/:id" element={<CasoDetallePage />} />
          <Route path="/metodologia" element={<MetodologiaPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}
