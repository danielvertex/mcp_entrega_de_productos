# Delivery App MCP

Una potente aplicación basada en el Model Context Protocol (MCP) para la gestión y optimización de rutas de entrega en tiempo real. Diseñada específicamente para transportistas y servicios de logística que buscan eficiencia operativa y una interfaz reactiva premium.

## Caracteristicas Principales

-   Gestion de Puntos Dinamica: Agrega, elimina y marca estados de entrega (Entregado, Fallido, Re-programado) con actualización instantánea.
-   Navegacion Inteligente: Genera enlaces automáticos a Google Maps para el trayecto actual y el siguiente punto sugerido.
-   Optimizacion de Rutas: Utiliza servicios de ruteo (OSRM con fallback de Haversine) para calcular la secuencia más eficiente de entregas.
-   Control de Gastos: Cálculo automático de consumo de combustible y costos operativos basados en el rendimiento del vehículo.
-   Historial Detallado: Registro de jornadas cerradas con títulos descriptivos y marcas de tiempo en Horario Central de México (Aguascalientes).
-   UI Reactiva: Interfaz construida con prefab-ui que responde instantáneamente a cada acción sin recargar la página.

## Instalacion y Ejecucion

### Requisitos
-   Python 3.12 o superior.
-   Acceso a internet (para servicios de mapas y ruteo).

### Configuracion del Entorno
1.  Clona el repositorio.
2.  Instala el paquete en modo editable:
    ```bash
    pip install -e .
    ```

### Ejecucion en Modo Desarrollo
Para lanzar la aplicación con el inspector y la interfaz de desarrollo:
```bash
fastmcp dev apps delivery_app/server.py --mcp-port 8081 --dev-port 8086
```
La interfaz estará disponible en `http://localhost:8086`.

## Estructura del Proyecto

-   `apps/delivery_app/server.py`: Punto de entrada de la aplicación FastMCP.
-   `delivery_app/domain/`: Lógica de negocio pura y modelos (Trip, Delivery, Metrics).
-   `delivery_app/services/`: Orquestación de servicios (TripService, RoutingService).
-   `delivery_app/tools/`: Definición de herramientas MCP para la gestión de datos.
-   `delivery_app/ui/`: Construcción de la interfaz de usuario reactiva.
-   `delivery_app/infrastructure/`: Persistencia en archivos JSON atómicos.

## Notas Tecnicas

-   Zona Horaria: La aplicación está configurada para usar America/Mexico_City (UTC-6), garantizando que los registros del historial coincidan con la hora local de Aguascalientes, México.
-   Persistencia: Los datos se guardan en el directorio data/ en formato JSON, asegurando escrituras atómicas para evitar corrupción de archivos.

---
Desarrollado como parte del ecosistema MCP para Advanced Agentic Coding.
