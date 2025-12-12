import voyager.intelligence.context.context_builder as cb


def test_context_builder_module_imports():
    # Minimal Phase 9 contract: module must import without errors.
    assert cb is not None
