export default function execOnce<T extends (...args: any[]) => ReturnType<T>>(fn: T): T;
