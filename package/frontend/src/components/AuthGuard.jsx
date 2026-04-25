import React from 'react';
import { Navigate } from 'react-router-dom';

const AuthGuard = ({ children }) => {
  const userToken = localStorage.getItem('userToken');
  return userToken ? children : <Navigate to="/login" replace />;
};

export default AuthGuard;
