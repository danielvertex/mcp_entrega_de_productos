# AGENTS.md

## Objetivo
Este proyecto es una app MCP en Python para gestión y optimización de rutas de entrega. Toda modificación debe priorizar confiabilidad operativa, claridad arquitectónica y seguridad del estado.

## Arquitectura
- Separar UI, tools, domain, services e infrastructure.
- Usar FastMCPApp para apps con varias acciones backend.
- No mezclar lógica de negocio con componentes Prefab UI.
- No mezclar persistencia con reglas de dominio.
- No mezclar clientes HTTP externos con cálculo de negocio.

## Reglas de implementación
- Antes de cambios grandes, crear plan y listar archivos afectados.
- Preferir cambios pequeños y coherentes.
- Mantener compatibilidad funcional cuando sea razonable.
- Usar nombres explícitos y funciones pequeñas.
- Usar enums para estados y modos.
- Todo input externo debe validarse con Pydantic o validación equivalente.
- Toda operación crítica debe manejar errores de forma explícita.

## Reglas de producto
- No usar la palabra “óptimo” salvo prueba exacta.
- Si la ruta viene de fallback, mostrarlo como estimación.
- Separar siempre ubicación actual de última entrega completada.
- Cierre de día debe ser idempotente.
- Toda acción destructiva requiere confirmación.
- Evitar doble submit y estados inconsistentes.

## Persistencia
- Escrituras atómicas obligatorias.
- Todo viaje debe tener trip_id único.
- Diseñar repositorios preparados para futura migración a SQLite/DB.
- No asumir single-user global.

## Testing
- Agregar tests unitarios para dominio.
- Agregar tests de integración para persistencia y routing.
- Agregar smoke tests para flujos críticos.
- No marcar trabajo como terminado sin tests relevantes.

## Seguridad
- No hardcodear secretos.
- No modificar auth sin justificarlo.
- Preparar interfaces para user_id/driver_id.
- Toda llamada externa debe estar envuelta con manejo de errores y timeouts.

## Entregables por tarea
- Resumen de cambios
- Riesgos
- Tests agregados o actualizados
- Pendientes detectados