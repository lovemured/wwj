function _define_property(obj, key, value) {
    if (key in obj) Object.defineProperty(obj, key, {
        value: value,
        enumerable: true,
        configurable: true,
        writable: true
    });
    else obj[key] = value;
    return obj;
}
class ServiceError extends Error {
    constructor(message, dump){
        super(message), _define_property(this, "dump", void 0);
        this.name = 'ServiceError';
        this.dump = dump;
    }
}
export { ServiceError };

//# sourceMappingURL=errors.mjs.map