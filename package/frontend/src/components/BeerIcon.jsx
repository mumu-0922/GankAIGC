import React from 'react';
import beerMugIcon from '../assets/beer-mug-twemoji.svg';

const BeerIcon = ({ className = 'w-4 h-4', alt = '', ...props }) => (
  <img
    src={beerMugIcon}
    alt={alt}
    aria-hidden={alt ? undefined : true}
    className={`inline-block shrink-0 object-contain ${className}`}
    {...props}
  />
);

export default BeerIcon;
