function initSearchableSelect(selector, options) {
    const el = document.querySelector(selector);
    if (!el) return null;

    const instance = new TomSelect(el, Object.assign({
        create: false,
        allowEmptyOption: false,
    }, options));

    if (el.classList.contains('is-invalid')) {
        instance.wrapper.classList.add('is-invalid');
    }

    return instance;
}
