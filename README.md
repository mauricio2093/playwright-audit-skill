# Playwright Auditor Skill

Repositorio orientado a una skill especializada en **Playwright** para automatizar auditorias web, generar pruebas E2E y producir reportes tecnicos listos para analisis o integracion en CI/CD.

## Que es este repositorio

Este proyecto reúne la documentacion, el prompt base y la estructura de una skill llamada **`playwright-auditor`**. Su objetivo es permitir que un agente o asistente pueda trabajar con Playwright de forma mas autonoma para:

- instalar y configurar Playwright
- descargar y resumir documentacion oficial
- generar suites de pruebas
- ejecutar auditorias funcionales, visuales, de accesibilidad y rendimiento
- producir reportes en Markdown con recomendaciones accionables

No es una aplicacion final para usuarios comunes; es una base de trabajo para crear, mantener o reutilizar una skill tecnica enfocada en testing web automatizado.

## Contenido principal

- `skills/playwright-auditor/SKILL.md`: instrucciones principales de uso.
- `skills/playwright-auditor/scripts/`: scripts para instalacion, scaffolding, ejecucion de auditorias y generacion de reportes.
- `skills/playwright-auditor/references/`: referencias tecnicas, buenas practicas, errores comunes y plantillas de CI/CD.

## Para que sirve

Este repositorio puede ser util si quieres:

- auditar un sitio web con Playwright
- acelerar la creacion de pruebas E2E
- estandarizar reportes tecnicos de testing
- integrar validaciones automatizadas en pipelines
- contar con una skill reutilizable para agentes de IA o flujos de QA

## Flujo general

1. Instalar Playwright y sus dependencias.
2. Consultar o actualizar referencias oficiales.
3. Generar pruebas segun el escenario deseado.
4. Ejecutar la auditoria.
5. Generar un reporte con hallazgos y recomendaciones.

## Enfoque del proyecto

El repositorio esta pensado con una orientacion tecnica y modular: separa instrucciones, scripts y referencias para que la skill pueda evolucionar, reutilizarse en otros entornos y adaptarse a distintos proyectos web.
