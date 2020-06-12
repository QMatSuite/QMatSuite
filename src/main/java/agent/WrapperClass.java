/*******************************************************************************
 * Copyright (c) 2020 Haonan Huang.
 *
 *     This file is part of QuantumVITAS (Quantum Visualization Interactive Toolkit for Ab-initio Simulations).
 *
 *     QuantumVITAS is free software: you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation, either version 3 of the License, or
 *     any later version.
 *
 *     QuantumVITAS is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU General Public License for more details.
 *
 *     You should have received a copy of the GNU General Public License
 *     along with QuantumVITAS.  If not, see <https://www.gnu.org/licenses/gpl-3.0.txt>.
 *******************************************************************************/
package main.java.agent;

import java.io.Serializable;

public abstract class WrapperClass implements Serializable{
	/**
	 * 
	 */
	private static final long serialVersionUID = -7585441076371339484L;
	
	protected Boolean enabled=true;
	public void setEnabled(Boolean bl) {
		enabled=bl;
	}
	public Boolean isEnabled() {
		return enabled;
	}
	public abstract Boolean isNull();
	public abstract Boolean isDefaultNull();
}
