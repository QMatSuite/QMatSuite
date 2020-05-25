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

import com.consts.ChemicalElements;

import javafx.scene.control.Alert;
import javafx.scene.control.Alert.AlertType;

public class Atom implements Serializable{
	/**
	 * 
	 */
	private static final long serialVersionUID = 2080346685186523233L;
	
	private ChemicalElements atomSpecies;
	//coordinates "as is"
	private Coordinate x_coor;
	private Coordinate y_coor;
	private Coordinate z_coor;
	//for magnet
	private Double mag;private Double angle1;private Double angle2;

	
	public Atom(ChemicalElements species, Double x, Double y, Double z, Boolean fix_x,Boolean fix_y,Boolean fix_z) {
		atomSpecies = species;
		x_coor=new Coordinate(x,fix_x);
		y_coor=new Coordinate(y,fix_y);
		z_coor=new Coordinate(z,fix_z);
		mag=0.0;angle1=0.0;angle2=0.0;
	}
	public Atom(String species, Double x, Double y, Double z, Boolean fix_x,Boolean fix_y,Boolean fix_z) {
		try {
			atomSpecies = ChemicalElements.valueOf(species);
		}catch(IllegalArgumentException e) {
			Alert alert1 = new Alert(AlertType.INFORMATION);
	    	alert1.setTitle("Error");
	    	alert1.setContentText("Invalid atom found in Atom class!"+e.getMessage());
	    	alert1.showAndWait();
			e.printStackTrace();
		}
		x_coor=new Coordinate(x,fix_x);
		y_coor=new Coordinate(y,fix_y);
		z_coor=new Coordinate(z,fix_z);
		mag=0.0;angle1=0.0;angle2=0.0;
	}
	public void mulX(Double mul) {
		if (mul!=null) {
			double tmp=x_coor.getX();
			x_coor.setX(tmp*mul);}
	}
	public void mulY(Double mul) {
		if (mul!=null) {
			double tmp=y_coor.getX();
			y_coor.setX(tmp*mul);}
	}
	public void mulZ(Double mul) {
		if (mul!=null) {
			double tmp=z_coor.getX();
			z_coor.setX(tmp*mul);}
	}
	public ChemicalElements getAtomSpecies() {
		return atomSpecies;
	}
	public void setAtomSpecies(ChemicalElements atomSpecies) {
		this.atomSpecies = atomSpecies;
	}
	public Coordinate getX_coor() {
		return x_coor;
	}
	public void setX_coor(Coordinate x_coor) {
		this.x_coor = x_coor;
	}
	public Coordinate getY_coor() {
		return y_coor;
	}
	public void setY_coor(Coordinate y_coor) {
		this.y_coor = y_coor;
	}
	public Coordinate getZ_coor() {
		return z_coor;
	}
	public void setZ_coor(Coordinate z_coor) {
		this.z_coor = z_coor;
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
