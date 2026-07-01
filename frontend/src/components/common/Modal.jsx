function Modal({ children, className = "modal-backdrop" }) {
  return <div className={className} role="presentation">{children}</div>;
}

export default Modal;
