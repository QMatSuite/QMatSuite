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

public class Element implements Serializable{
	/**
	 * 
	 */
	private static final long serialVersionUID = 1452087912861807366L;
	
	private ChemicalElements atomSpecies;
	private Double atomMass;
	private String pseudoPotFile;
	private boolean pseudoValid;
	private Double hubbardU;
	private Double mag;private Double angle1;private Double angle2;
	
	public Element(ChemicalElements species) {
		atomSpecies = species;
		pseudoPotFile = null;pseudoValid=false;
		hubbardU = 0.0;mag=0.0;angle1=0.0;angle2=0.0;
		atomMass=species.getAtomicMass();
//		try {
//			ChemicalElements enumElem = ChemicalElements.valueOf(species);
//			atomMass=enumElem.getAtomicMass();
//		}catch(IllegalArgumentException e) {
//			Alert alert1 = new Alert(AlertType.INFORMATION);
//	    	alert1.setTitle("Error");
//	    	alert1.setContentText("Exception in Element class!"+e.getMessage());
//	    	alert1.showAndWait();
//			e.printStackTrace();
//		}
	}
	public Element(ChemicalElements species, Double hubb) {
		atomSpecies = species;
		pseudoPotFile = null;pseudoValid=false;
		hubbardU = hubb;mag=0.0;angle1=0.0;angle2=0.0;
		atomMass=species.getAtomicMass();
//		try {
//			ChemicalElements enumElem = ChemicalElements.valueOf(species);
//			atomMass=enumElem.getAtomicMass();
//		}catch(IllegalArgumentException e) {
//			Alert alert1 = new Alert(AlertType.INFORMATION);
//	    	alert1.setTitle("Error");
//	    	alert1.setContentText("Exception in Element class!"+e.getMessage());
//	    	alert1.showAndWait();
//			e.printStackTrace();
//		}
	}
	public Element(String species, Double hubb) {
		pseudoPotFile = null;pseudoValid=false;
		hubbardU = hubb;mag=0.0;angle1=0.0;angle2=0.0;
		try {
			atomSpecies = ChemicalElements.valueOf(species);
			atomMass=atomSpecies.getAtomicMass();
		}catch(IllegalArgumentException e) {
			Alert alert1 = new Alert(AlertType.INFORMATION);
	    	alert1.setTitle("Error");
	    	alert1.setContentText("Exception in Element class!"+e.getMessage());
	    	alert1.showAndWait();
			e.printStackTrace();
		}
	}
	public ChemicalElements getAtomSpecies() {
		return atomSpecies;
	}
	public void setAtomSpecies(ChemicalElements atomSpecies) {
		this.atomSpecies = atomSpecies;
		this.atomMass=atomSpecies.getAtomicMass();
	}
	public Double getAtomMass() {
		return atomMass;
	}
	public void setAtomMass(Double atomMass) {
		this.atomMass = atomMass;
	}
	public String getPseudoPotFile() {
		return pseudoPotFile;
	}
	public void setPseudoPotFile(String pseudoPotFile) {
		this.pseudoPotFile = pseudoPotFile;
	}
	public Double getHubbardU() {
		return hubbardU;
	}
	public void setHubbardU(Double hubbardU) {
		if (hubbardU!=null) this.hubbardU = hubbardU;
	}
	public Double getMag() {
		return mag;
	}
	public void setMag(Double mag) {
		if (mag!=null)  this.mag = mag;
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
	public boolean isPseudoValid() {
		return pseudoValid;
	}
	public void setPseudoValid(boolean pseudoValid) {
		this.pseudoValid = pseudoValid;
	}
}
