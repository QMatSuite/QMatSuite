/*******************************************************************************
 * Copyright (c) 2020 Haonan Huang.
 *
 *     This file is part of QuantumVITAS (Quantum Visualization Interactive 
 *     Toolkit for Ab-initio Simulations).
 *
 *     QuantumVITAS is free software: you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation, either version 3 of the License, or any 
 *     later version.
 *
 *     QuantumVITAS is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU General Public License for more details.
 *
 *     You should have received a copy of the GNU General Public License
 *     along with QuantumVITAS.  If not, see <https://www.gnu.org/licenses/gpl-3.0.txt>.
 *******************************************************************************/
package app.input.geo;

import java.io.Serializable;

import core.com.consts.ChemicalElements;

public abstract class Chemical implements Serializable{

	/**
	 * 
	 */
	private static final long serialVersionUID = -1327835842150618434L;

	
	protected ChemicalElements atomSpecies;
	protected Double atomMass;
	protected Double mag;
	protected Double angle1;
	protected Double angle2;
	public Chemical(ChemicalElements species) {
		atomSpecies = species;
		atomMass=species.getAtomicMass();
		mag=0.0;angle1=0.0;angle2=0.0;
	}
	public Chemical() {
		atomSpecies = null;
		atomMass=null;
		mag=0.0;angle1=0.0;angle2=0.0;
	}
	public ChemicalElements getAtomSpecies() {
		return atomSpecies;
	}
	public void setAtomSpecies(ChemicalElements atomSpecies) {
		this.atomSpecies = atomSpecies;
		this.atomMass=atomSpecies.getAtomicMass();
	}
	public Double getMag() {
		return mag;
	}
	public void setMag(Double mag) {
		if (mag!=null) this.mag = mag;
	}
	public Double getAngle1() {
		return angle1;
	}
	public void setAngle1(Double angle1) {
		if (angle1!=null) this.angle1 = angle1;
	}
	public Double getAngle2() {
		return angle2;
	}
	public void setAngle2(Double angle2) {
		if (angle2!=null) this.angle2 = angle2;
	}
}
