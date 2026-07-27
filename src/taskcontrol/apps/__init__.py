"""Composition roots.

Each subpackage builds settings, configures logging, instantiates adapters, and starts
one process. Composition roots wire; they never define routes, command bodies, or
business rules (ADR 0019).
"""
