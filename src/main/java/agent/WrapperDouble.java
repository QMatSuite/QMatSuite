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
package agent;

public class WrapperDouble extends WrapperClass{
	/**
	 * 
	 */
	private static final long serialVersionUID = 1129334485712449681L;
	private Double value;
	final private Double defaultValue;
	
	public WrapperDouble(Double val) {
		defaultValue = val;
		value = val;
		enabled = false;
	}
	public WrapperDouble(Double val,Boolean bl) {
		defaultValue = val;
		value = val;
		enabled = bl;
	}
	public Double getValue() {
		return value;
	}
	public void setValue(Double val) {
		value = val;
	}
	public Boolean equals(Double vl) {
		return java.util.Objects.equals(vl, value);
	}
	@Override
	public Boolean isNull() {
		return value==null;
	}
	public Double resetDefault() {
		value = defaultValue;
		return defaultValue;
	}
	@Override
	public Boolean isDefaultNull() {
		return defaultValue==null;
	}
}
