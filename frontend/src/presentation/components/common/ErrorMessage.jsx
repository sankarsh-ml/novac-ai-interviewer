function ErrorMessage({ children, className = "error-message" }) {
  return children ? <p className={className}>{children}</p> : null;
}

export default ErrorMessage;
