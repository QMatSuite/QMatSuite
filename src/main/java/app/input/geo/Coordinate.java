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
package app.input.geo;

import java.io.Serializable;

public class Coordinate implements Serializable{
	/**
	 * 
	 */
	private static final long serialVersionUID = 6860062913275715116L;
	
	private Double x;
	private Boolean fix_x;
	public Coordinate(Double x,Boolean fix_x) {
		this.setX(x);
		this.setBoolFix(fix_x);
	}
	public String toString() {
		return x.toString();
	}
	public Boolean getBoolFix() {
		return fix_x;
	}
	public String getFixString() {
		if(fix_x==null) {return "null";}
		return fix_x?"fix":"free";
	}
	public void setBoolFix(Boolean fix_x) {
		this.fix_x = fix_x;
	}
	public Double getX() {
		return x;
	}
	public String getXString() {
		if(x==null) {return "null";}
		return x.toString();
	}
	public void setX(Double x) {
		this.x = x;
	}
}
